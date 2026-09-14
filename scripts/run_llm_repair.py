#!/usr/bin/env python3
"""Registered LLM repair runner (B2 unconstrained / B3 validator-grounded).

Runs agent episodes over the frozen partition with resumability: every
completed episode is appended to generated/llm-repair/episodes.jsonl, and
re-running skips keys already present.  Registered rows are rebuilt from the
ledger into data/results/detection_repair_llm.csv after each episode.

Usage (repo root, endpoint already serving):
  PYTHONPATH=src .venv/bin/python scripts/run_llm_repair.py --pilot
  PYTHONPATH=src .venv/bin/python scripts/run_llm_repair.py            # full
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from construction_scene_ready import llm_repair  # noqa: E402
from construction_scene_ready.detection_repair import (  # noqa: E402
    REPAIR_NOT_ATTEMPTED,
    to_registered_row,
)
from construction_scene_ready.fault_injection import inject_fault  # noqa: E402
from construction_scene_ready.partition import load_manifest  # noqa: E402
from construction_scene_ready.suites import build_scenes  # noqa: E402
from construction_scene_ready.validator import SceneValidator  # noqa: E402

TAXONOMY = REPO / "docs" / "fault-taxonomy.csv"
MANIFEST = REPO / "data" / "partition-manifest.json"
LEDGER = REPO / "generated" / "llm-repair" / "episodes.jsonl"
RESULT_CSV = REPO / "data" / "results" / "detection_repair_llm.csv"
RUN_ID = "B-CPU-LLM-0001"

PILOT_FAULTS = ("wrong_up_axis", "nonpositive_mass", "mismatched_task_interface_target",
                "unsupported_generated_friction", "missing_interface_axis",
                "compound_task_contract")
PILOT_SEEDS = (0, 1)


def git_sha() -> str:
    import subprocess
    return subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, cwd=REPO,
    ).stdout.strip()


def load_ledger() -> dict[tuple, dict]:
    done = {}
    if LEDGER.exists():
        for line in LEDGER.open(encoding="utf-8"):
            rec = json.loads(line)
            key = (rec["partition"], rec["scene_id"], rec["fault_id"],
                   rec["method"], rec["seed"])
            done[key] = rec
    return done


def episode_to_row(rec: dict) -> dict:
    case = {
        "scene_id": rec["scene_id"], "fault_id": rec["fault_id"],
        "partition": rec["partition"], "fault_family": rec["fault_family"],
        "method": rec["method"], "seed": rec["seed"],
        "true_positive": rec["tp"], "false_positive": rec["fp"],
        "false_negative": rec["fn"], "detected": rec["critical_detected"],
        "repair_outcome": rec["outcome"],
        "validation_ms": 0.0, "repair_ms": rec["episode_s"] * 1000.0,
    }
    row = to_registered_row(case)
    row["iterations"] = 1
    row["time_s"] = round(rec["episode_s"], 3)
    return row


def rebuild_csv(done: dict) -> None:
    RESULT_CSV.parent.mkdir(parents=True, exist_ok=True)
    from construction_scene_ready.detection_repair import CSV_FIELDS
    with RESULT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for key in sorted(done):
            writer.writerow(episode_to_row(done[key]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--methods", default="b2,b3")
    args = parser.parse_args()

    methods = tuple(m.strip() for m in args.methods.split(","))
    manifest = load_manifest(MANIFEST, TAXONOMY)
    roles = {row["fault_id"]: row for row in
             csv.DictReader(TAXONOMY.open(encoding="utf-8"))}
    commit = git_sha()
    done = load_ledger()
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    ledger = LEDGER.open("a", encoding="utf-8")

    validator = SceneValidator()
    client = llm_repair._client()
    runners = {"b2": llm_repair.run_b2_case, "b3": llm_repair.run_b3_case,
               "a5": lambda s, f, sd, client=None: llm_repair.run_b3_case(s, f, sd, client=client, typed=False)}
    seeds = PILOT_SEEDS if args.pilot else llm_repair.SEEDS

    total = skipped = 0
    with tempfile.TemporaryDirectory(prefix="csr-llm-") as tmp:
        tmp_path = Path(tmp)
        scene_cache: dict[str, list[dict]] = {}
        for partition, spec in manifest["partitions"].items():
            key = f"{spec['scene_kind']}:{spec['variant_index']}"
            if key not in scene_cache:
                scene_cache[key] = build_scenes(
                    spec["scene_kind"], spec["variant_index"], tmp_path / key)
            for scene in scene_cache[key]:
                faults = [f for f in spec["faults"]
                          if not args.pilot or f in PILOT_FAULTS]
                for fault_id in faults:
                    for method in methods:
                        for seed in seeds:
                            total += 1
                            method_name = {"b2": "unconstrained-agent",
                                           "b3": "validator-grounded-agent",
                                           "a5": "ablation-prose-diagnostics"}[method]
                            k = (partition, scene["scene_id"], fault_id, method_name, seed)
                            if k in done:
                                skipped += 1
                                continue
                            start = time.perf_counter()
                            rec = runners[method](scene, fault_id, seed, client=client)
                            episode_s = time.perf_counter() - start
                            faulty = inject_fault(scene, fault_id)
                            expected = set(faulty["fault_ground_truth"]["expected_rules"])
                            before = validator.validate(faulty)
                            found = {i.rule_id for i in before.issues}
                            typed_detection = method in ("b3", "a5")
                            entry = {
                                "run_id": RUN_ID, "commit_sha": commit,
                                "partition": partition,
                                "scene_id": scene["scene_id"],
                                "fault_id": fault_id,
                                "fault_family": roles[fault_id]["family"],
                                "method": method_name, "seed": seed,
                                "tp": len(expected & found) if typed_detection else 0,
                                "fp": len(found - expected) if typed_detection else 0,
                                "fn": len(expected - found) if typed_detection else len(expected),
                                "critical_detected": int(expected <= found) if typed_detection else 0,
                                "outcome": rec["outcome"],
                                "parse_error": rec.get("parse_error", False),
                                "episode_s": round(episode_s, 3),
                                "prompt_version": rec["prompt_version"],
                                "model": llm_repair.MODEL_WEIGHTS,
                                "decoding": {"temperature": llm_repair.TEMPERATURE,
                                             "top_p": llm_repair.TOP_P,
                                             "max_tokens": llm_repair.MAX_TOKENS},
                                "llm_usage": {k2: rec["llm"].get(k2) for k2 in
                                              ("prompt_tokens", "completion_tokens", "finish_reason")},
                            }
                            ledger.write(json.dumps(entry, ensure_ascii=False) + "\n")
                            ledger.flush()
                            done[k] = entry
                            print(f"[{len(done)}] {method_name} {fault_id} s{seed}: "
                                  f"{entry['outcome']} ({episode_s:.1f}s)", flush=True)
                            rebuild_csv(done)
    print(f"total={total} skipped={skipped} new={total - skipped} -> {RESULT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
