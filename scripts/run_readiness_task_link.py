#!/usr/bin/env python3
"""H4 redo: validator readiness score vs measured humanoid task success.

Bridges the humanoid defect benchmark (Isaac-Assembly-G1, RL insertion policy,
per-episode JSONL in ~/ZCodeProject/logs/defects) with the scene contract:
each runtime defect condition is re-expressed as its scene-contract equivalent
fault on the matching CSR fixture scenario (pin_insertion) and scored by the
real SceneValidator.  readiness_score = fraction of the 30 scene-readiness
rules not violated.

Conditions with no mapped scene fault are *sub-rule fidelity* defects
(coordinate/clearance errors inside declared tolerances): the validator is
silent on them by construction.  The analysis quantifies this blind spot as a
flagged-vs-consequential confusion matrix and registers candidate rules to
close it.

Outputs:
- data/results/task_outcomes.csv (registered schema, one row per episode)
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

import numpy as np

import sys
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from construction_scene_ready.fault_injection import inject_fault  # noqa: E402
from construction_scene_ready.suites import build_scenes  # noqa: E402
from construction_scene_ready.validator import SceneValidator  # noqa: E402

DEFECT_LOGS = Path(os.path.expanduser("~/ZCodeProject/logs/defects_v2c"))
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
)


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def spearman(x: list[float], y: list[float]) -> float:
    def ranks(values):
        order = np.argsort(values)
        r = np.empty(len(values))
        r[order] = np.arange(len(values))
        return r
    rx, ry = ranks(x), ranks(y)
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def load_episodes(tag: str, seed: int) -> list[dict]:
    path = DEFECT_LOGS / f"{tag}_s{seed}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.open(encoding="utf-8")]


def load_episodes_n1000(tag: str) -> list[dict]:
    path = DEFECT_LOGS / f"{tag}_n1000_s42.jsonl"
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
                })
            if episodes:
                stats = condition_stats.setdefault(condition, {})
                stats[seed] = {
                    "episodes": len(episodes),
                    "success_rate": sum(e["success"] for e in episodes) / len(episodes),
                }

    # McNemar per condition vs none, per seed (paired by env/episode).
    # Geometry conditions additionally use the power-upgraded n=1000 batch,
    # which is the definitive test for small severities.
    n1000_conditions = {"geometry_2mm", "geometry_5mm", "geometry_10mm", "geometry_member_10mm"}
    for condition, stats in condition_stats.items():
        if condition == "none":
            continue
        for seed, st in stats.items():
            base = {(e["env"], e["episode"]): e["success"] for e in load_episodes("none", seed)}
            cond = {(e["env"], e["episode"]): e["success"] for e in load_episodes(condition, seed)}
            keys = sorted(set(base) & set(cond))
            b = sum(1 for k in keys if base[k] and not cond[k])
            c = sum(1 for k in keys if not base[k] and cond[k])
            st["mcnemar_b"] = b
            st["mcnemar_c"] = c
            st["mcnemar_p"] = mcnemar_exact(b, c)
        if condition in n1000_conditions:
            base = {(e["env"], e["episode"]): e["success"]
                    for e in load_episodes_n1000("none")}
            cond = {(e["env"], e["episode"]): e["success"]
                    for e in load_episodes_n1000(condition)}
            keys = sorted(set(base) & set(cond))
            b = sum(1 for k in keys if base[k] and not cond[k])
            c = sum(1 for k in keys if not base[k] and cond[k])
            stats["n1000_s42"] = {
                "episodes": len(cond),
                "success_rate": sum(cond.values()) / max(1, len(cond)),
                "mcnemar_b": b, "mcnemar_c": c, "mcnemar_p": mcnemar_exact(b, c),
            }

    # flagged vs consequential confusion.  Consequential = significant in the
    # most powered available test: the n=1000 batch for geometry conditions,
    # otherwise both 200-episode seed partitions.
    def is_consequential(condition: str, stats: dict) -> bool:
        if not stats:
            return False
        if condition in n1000_conditions and "n1000_s42" in stats:
            return stats["n1000_s42"]["mcnemar_p"] < 0.05
        seed_stats = [st for key, st in stats.items() if str(key).isdigit()]
        return all(st.get("mcnemar_p", 1.0) < 0.05 for st in seed_stats)

    confusion = {"tp": [], "fp": [], "fn": [], "tn": []}
    for condition in CONDITION_FAULT:
        if condition == "none":
            continue
        flagged = readiness[condition] < 1.0
        consequential = is_consequential(condition, condition_stats.get(condition, {}))
        cell = ("tp" if consequential else "fp") if flagged else ("fn" if consequential else "tn")
        confusion[cell].append(condition)

    xs, ys = [], []
    for condition in CONDITION_FAULT:
        if condition == "none" or condition not in condition_stats:
            continue
        rate = np.mean([
            st["success_rate"]
            for key, st in condition_stats[condition].items()
            if str(key).isdigit()
        ])
        xs.append(readiness[condition])
        ys.append(rate)

    report = {
        "readiness_rule_count": RULE_COUNT,
        "scenario_proxy": SCENARIO_PROXY,
        "readiness": readiness,
        "violated_rules": violated,
        "condition_stats": condition_stats,
        "spearman_readiness_success": spearman(xs, ys),
        "confusion": confusion,
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
    print(f"spearman(readiness, success) = {report['spearman_readiness_success']:.3f}")
    print(f"sensitivity={report['validator_sensitivity']:.3f} specificity={report['validator_specificity']:.3f}")
    for cell in ("tp", "fp", "fn", "tn"):
        print(f"  {cell}: {confusion[cell]}")
    print(f"-> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
