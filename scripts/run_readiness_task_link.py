#!/usr/bin/env python3
"""H4 redo: validator readiness score vs measured humanoid task success.

Bridges the humanoid defect benchmark (Isaac-Assembly-G1, RL insertion policy,
per-episode JSONL from the simultaneous reward+geometric evaluator in
~/ZCodeProject/logs/defects_geo*, seed 42 and 123) with the scene contract:
each runtime defect condition is re-expressed as its scene-contract equivalent
fault on the matching CSR fixture scenario (pin_insertion) and scored by the
real SceneValidator.  readiness_score = fraction of the 30 scene-readiness
rules not violated.

Conditions with no mapped scene fault are *sub-rule fidelity* defects
(coordinate/clearance errors inside declared tolerances): the validator is
silent on them by construction.  The analysis quantifies this blind spot as a
flagged-vs-consequential confusion matrix and registers candidate rules to
close it.  A condition is consequential if it significantly degrades the
paired geometric-valid outcome (exact McNemar, seed-42 partition); the
reward-criterion confusion is retained as an auxiliary view.

Outputs:
- data/results/task_outcomes.csv (registered schema, one row per episode,
  with the simultaneous geometric_valid flag)
- generated/readiness-task-link/report.json
"""

from __future__ import annotations

import csv
import glob
import json
import os
import tempfile
from math import comb
from pathlib import Path

import sys
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from construction_scene_ready.fault_injection import inject_fault  # noqa: E402
from construction_scene_ready.suites import build_scenes  # noqa: E402
from construction_scene_ready.validator import SceneValidator  # noqa: E402

#: per-seed episode logs from the simultaneous reward+geometric evaluator
#: (eval_defect_geo.py); both metrics are recorded at the same timestep
DEFECT_LOGS = {
    42: Path(os.path.expanduser("~/ZCodeProject/logs/defects_geo")),
    123: Path(os.path.expanduser("~/ZCodeProject/logs/defects_geo_s123")),
}
RESULT_CSV = REPO / "data" / "results" / "task_outcomes.csv"
REPORT = REPO / "generated" / "readiness-task-link" / "report.json"
RULE_COUNT = 30
SCENARIO_PROXY = "pin_insertion"
HUMANOID_SCENARIO = "g1_steel_bolt_insertion"
METHOD = "rl-insertion-policy"
TASK_LEVEL = "fixed_base"

#: defect condition -> equivalent scene-contract fault (None = sub-rule fidelity)
CONDITION_FAULT = {
    "none": None,
    "geometry_2mm": None,
    "geometry_5mm": None,
    "geometry_10mm": None,
    "geometry_member_10mm": None,
    "interface_0.75mm": None,
    "interface_0.5mm": None,
    "interface_0.25mm": None,
    "semantic_missing": "missing_ifc_guid",
    "semantic_wrong": "duplicate_ifc_guid",
    "task_ref": "mismatched_task_interface_target",
    "state": "invalid_construction_state",
    "physics_half": None,
    "physics_double": None,
}

CSV_FIELDS = (
    "case_id", "scenario", "task_level", "method", "seed", "readiness_score",
    "planning_success", "grasp_success", "alignment_success",
    "insertion_success", "full_task_success", "failure_cause",
    "geometric_valid",
)


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def load_episodes(tag: str, seed: int) -> list[dict]:
    path = DEFECT_LOGS[seed] / f"{tag}_s{seed}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.open(encoding="utf-8")]


def main() -> int:
    validator = SceneValidator()
    with tempfile.TemporaryDirectory(prefix="csr-h4-") as tmp:
        scenes = build_scenes("variant", 1, Path(tmp))
        pristine = next(s for s in scenes if s["scene_id"].startswith(SCENARIO_PROXY))

    readiness: dict[str, float] = {}
    violated: dict[str, list[str]] = {}
    for condition, fault in CONDITION_FAULT.items():
        scene = inject_fault(pristine, fault) if fault else pristine
        issues = validator.validate(scene).issues
        rules = sorted({issue.rule_id for issue in issues})
        violated[condition] = rules
        readiness[condition] = round((RULE_COUNT - len(rules)) / RULE_COUNT, 4)

    rows = []
    condition_stats: dict[str, dict] = {}
    for condition in CONDITION_FAULT:
        for seed in (42, 123):
            episodes = load_episodes(condition, seed)
            for ep in episodes:
                success = bool(ep["success"])
                geo = bool(ep.get("geo_success", False))
                if success:
                    cause = ""
                elif ep["min_perp_mm"] >= 12.0:
                    cause = "misalignment"
                else:
                    cause = "insufficient_depth"
                rows.append({
                    "case_id": f"{condition}__s{seed}__e{ep['env']:03d}__ep{ep['episode']}",
                    "scenario": HUMANOID_SCENARIO,
                    "task_level": TASK_LEVEL,
                    "method": METHOD,
                    "seed": seed,
                    "readiness_score": readiness[condition],
                    "planning_success": "",
                    "grasp_success": "",
                    "alignment_success": "",
                    "insertion_success": int(success),
                    "full_task_success": int(success),
                    "failure_cause": cause,
                    "geometric_valid": int(geo),
                })
            if episodes:
                stats = condition_stats.setdefault(condition, {})
                stats[seed] = {
                    "episodes": len(episodes),
                    "success_rate": sum(e["success"] for e in episodes) / len(episodes),
                    "geo_rate": sum(bool(e.get("geo_success", False)) for e in episodes) / len(episodes),
                }

    # McNemar per condition vs none, per seed (paired by env/episode), on both
    # the reward criterion and the simultaneous geometric-valid criterion.
    for condition, stats in condition_stats.items():
        if condition == "none":
            continue
        for seed, st in stats.items():
            if not str(seed).isdigit():
                continue
            base_eps = load_episodes("none", seed)
            cond_eps = load_episodes(condition, seed)
            base = {(e["env"], e["episode"]): e["success"] for e in base_eps}
            cond = {(e["env"], e["episode"]): e["success"] for e in cond_eps}
            keys = sorted(set(base) & set(cond))
            b = sum(1 for k in keys if base[k] and not cond[k])
            c = sum(1 for k in keys if not base[k] and cond[k])
            st["mcnemar_b"] = b
            st["mcnemar_c"] = c
            st["mcnemar_p"] = mcnemar_exact(b, c)
            gbase = {(e["env"], e["episode"]): bool(e.get("geo_success", False)) for e in base_eps}
            gcond = {(e["env"], e["episode"]): bool(e.get("geo_success", False)) for e in cond_eps}
            gkeys = sorted(set(gbase) & set(gcond))
            gb = sum(1 for k in gkeys if gbase[k] and not gcond[k])
            gc = sum(1 for k in gkeys if not gbase[k] and gcond[k])
            st["geo_mcnemar_b"] = gb
            st["geo_mcnemar_c"] = gc
            st["geo_mcnemar_p"] = mcnemar_exact(gb, gc)

    # flagged vs consequential confusion.  Primary criterion: a condition is
    # consequential if it significantly degrades the paired geometric-valid
    # outcome (exact McNemar, seed-42 partition, matching the manuscript).
    # The reward-criterion confusion is kept as an auxiliary view.
    def is_consequential_geo(condition: str, stats: dict) -> bool:
        st = (stats or {}).get(42)
        return bool(st) and st.get("geo_mcnemar_p", 1.0) < 0.05

    def is_consequential_reward(condition: str, stats: dict) -> bool:
        st = (stats or {}).get(42)
        return bool(st) and st.get("mcnemar_p", 1.0) < 0.05

    def build_confusion(consequential_fn) -> dict[str, list]:
        conf = {"tp": [], "fp": [], "fn": [], "tn": []}
        for condition in CONDITION_FAULT:
            if condition == "none":
                continue
            flagged = readiness[condition] < 1.0
            consequential = consequential_fn(condition, condition_stats.get(condition, {}))
            cell = ("tp" if consequential else "fp") if flagged else ("fn" if consequential else "tn")
            conf[cell].append(condition)
        return conf

    confusion = build_confusion(is_consequential_geo)
    confusion_reward = build_confusion(is_consequential_reward)

    report = {
        "readiness_rule_count": RULE_COUNT,
        "scenario_proxy": SCENARIO_PROXY,
        "readiness": readiness,
        "violated_rules": violated,
        "condition_stats": condition_stats,
        "confusion": confusion,
        "confusion_criterion": "geometric-valid (simultaneous), exact McNemar seed 42",
        "confusion_reward": confusion_reward,
        "validator_sensitivity": len(confusion["tp"]) / max(1, len(confusion["tp"]) + len(confusion["fn"])),
        "validator_specificity": len(confusion["tn"]) / max(1, len(confusion["tn"]) + len(confusion["fp"])),
        "candidate_rules": [
            "CSR-SCN-031 (candidate): member-relative interface coordinates shall "
            "match the evidence model within the declared tolerance",
            "CSR-SCN-032 (candidate): interface clearance shall exceed the fastener "
            "envelope by the task-required minimum",
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    RESULT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with RESULT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"rows={len(rows)} -> {RESULT_CSV}")
    print(f"[geo] sensitivity={report['validator_sensitivity']:.3f} specificity={report['validator_specificity']:.3f}")
    for cell in ("tp", "fp", "fn", "tn"):
        print(f"  {cell}: {confusion[cell]}")
    print("[reward] auxiliary confusion:")
    for cell in ("tp", "fp", "fn", "tn"):
        print(f"  {cell}: {confusion_reward[cell]}")
    print(f"-> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
