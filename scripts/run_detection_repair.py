#!/usr/bin/env python3
"""Registered detection/repair experiment runner.

Freezes (or verifies) the partition manifest, builds the scene suite per
partition (base fixtures for development, variant index 1 for test/challenge),
runs every registered deterministic method over every case, and writes the
tidy result file data/results/detection_repair.csv plus a run report.

Usage (repo root):
  PYTHONPATH=src .venv/bin/python scripts/run_detection_repair.py [--freeze-manifest]
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from construction_scene_ready.detection_repair import (  # noqa: E402
    METHODS,
    run_case,
    summarize,
    write_rows,
    write_summary,
)
from construction_scene_ready.fixtures import (  # noqa: E402
    generate_fixture,
    scenario_specs,
    scenario_variant_specs,
)
from construction_scene_ready.ifc_parser import compile_ifc  # noqa: E402
from construction_scene_ready.partition import (  # noqa: E402
    build_manifest,
    load_manifest,
    write_manifest,
)

TAXONOMY = REPO / "docs" / "fault-taxonomy.csv"
MANIFEST = REPO / "data" / "partition-manifest.json"
RESULT_CSV = REPO / "data" / "results" / "detection_repair.csv"
REGISTRY = REPO / "docs" / "experiment-registry.csv"
VALIDATOR_VERSION = "0.2.0"


def git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True, cwd=REPO,
        ).stdout.strip()
    except Exception:
        return ""


def build_scenes(scene_kind: str, variant_index: int, workdir: Path) -> list[dict]:
    if scene_kind == "base":
        specs = list(scenario_specs())
    else:
        specs = [
            spec
            for spec in scenario_variant_specs(variant_index + 1)
            if spec.base_scene_id is not None
            and spec.scene_id.endswith(f"__v{variant_index:03d}")
        ]
    scenes = []
    for spec in specs:
        ifc_path, _truth = generate_fixture(spec, workdir)
        scenes.append(compile_ifc(ifc_path))
    return scenes


def update_registry(updates: dict[str, dict[str, str]]) -> None:
    """Fill commit/status/report columns of registered (planned) run rows."""
    with REGISTRY.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0].keys())
    for row in rows:
        patch = updates.get(row["run_id"])
        if patch:
            row.update(patch)
    with REGISTRY.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-manifest", action="store_true",
                        help="write the frozen partition manifest and exit")
    parser.add_argument("--run-id", default="B-CPU-DETREp-0001")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    if args.freeze_manifest:
        manifest = build_manifest(TAXONOMY)
        write_manifest(manifest, MANIFEST)
        counts = {k: len(v["faults"]) for k, v in manifest["partitions"].items()}
        print(f"froze {MANIFEST} partitions={counts}")
        return 0

    manifest = load_manifest(MANIFEST, TAXONOMY)
    commit = git_sha()
    roles = {row["fault_id"]: row for row in
             __import__("csv").DictReader(TAXONOMY.open(encoding="utf-8"))}

    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="csr-detrep-") as tmp:
        tmp_path = Path(tmp)
        scene_cache: dict[str, list[dict]] = {}
        for partition, spec in manifest["partitions"].items():
            key = f"{spec['scene_kind']}:{spec['variant_index']}"
            if key not in scene_cache:
                scene_cache[key] = build_scenes(
                    spec["scene_kind"], spec["variant_index"], tmp_path / key
                )
            scenes = scene_cache[key]
            for scene in scenes:
                for fault_id in spec["faults"]:
                    for method in METHODS:
                        rows.append(run_case(
                            scene, fault_id, roles[fault_id]["family"], method,
                            run_id=args.run_id, commit_sha=commit,
                            partition=partition, seed=args.seed,
                        ))

    write_rows(rows, RESULT_CSV)
    report_dir = REPO / "generated" / "detection-repair" / args.run_id
    summary = summarize(rows)
    summary["_meta"] = {
        "run_id": args.run_id, "commit_sha": commit, "seed": args.seed,
        "manifest_sha256": manifest["taxonomy_sha256"],
        "cases_per_method": len(rows) // len(METHODS),
        "methods": list(METHODS),
    }
    write_summary(summary, report_dir / "summary.json")

    update_registry({
        "B0-CPU-0001": {"commit_sha": commit, "status": "complete",
                        "report_path": str(report_dir / "summary.json")},
        "B1-CPU-0001": {"commit_sha": commit, "status": "complete",
                        "report_path": str(report_dir / "summary.json")},
    })

    print(f"cases={len(rows)} methods={len(METHODS)} -> {RESULT_CSV}")
    print(json.dumps(summary["_meta"], indent=2))
    for method, metrics in summary.items():
        if method.startswith("_"):
            continue
        print(f"  {method:<28} detected={metrics['detected_rate']:.3f} "
              f"valid={metrics['valid_repair_rate']:.3f} "
              f"escalated={metrics['escalation_rate']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
