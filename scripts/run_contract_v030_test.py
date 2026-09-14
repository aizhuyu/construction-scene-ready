#!/usr/bin/env python3
"""Contract v0.3.0 independent test: do the post-blind-spot rules detect
sub-tolerance interface defects on scenes the benchmark never used?

Test set: variant index 2 scenes (development/test used base and variant 1).
Per scene: pristine, drift-1mm (within tolerance: must PASS),
drift-5mm (beyond tolerance evidence: CSR-SCN-031), missing origin evidence
(CSR-SCN-031), clearance below task-required minimum (CSR-SCN-032).
Also verifies the v0.2.0 contract is blind to the 5 mm drift (the original
blind spot) and that pristine scenes pass v0.3.0 (no false positives).

Output: generated/contract-v030/report.json
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from construction_scene_ready.suites import build_scenes  # noqa: E402
from construction_scene_ready.validator import SceneValidator  # noqa: E402


def drift_origin(scene, mm):
    out = copy.deepcopy(scene)
    out["interfaces"][0]["origin_m"][0] += mm / 1000.0  # x 方向漂移
    return out


def drop_origin_evidence(scene):
    out = copy.deepcopy(scene)
    out["provenance"] = [r for r in out["provenance"] if r.get("property") != "origin_m"]
    return out


def clearance_below_minimum(scene):
    out = copy.deepcopy(scene)
    out["interfaces"][0]["required_clearance_mm"] = 5.0  # 任务要求高于声明容差
    return out


CONDITIONS = {
    "pristine": lambda s: s,
    "drift_1mm_within_tolerance": lambda s: drift_origin(s, 1.0),
    "drift_5mm_beyond_tolerance": lambda s: drift_origin(s, 5.0),
    "origin_evidence_missing": drop_origin_evidence,
    "clearance_below_minimum": clearance_below_minimum,
}

# 每个条件的预期: (v0.3.0 应通过?, 应触发的规则)
EXPECT = {
    "pristine": (True, set()),
    "drift_1mm_within_tolerance": (True, set()),
    "drift_5mm_beyond_tolerance": (False, {"CSR-SCN-031"}),
    "origin_evidence_missing": (False, {"CSR-SCN-031"}),
    "clearance_below_minimum": (False, {"CSR-SCN-032"}),
}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="csr-v030-") as tmp:
        scenes = build_scenes("variant", 2, Path(tmp))

    v020 = SceneValidator(contract_version="0.2.0")
    v030 = SceneValidator(contract_version="0.3.0")
    rows = []
    for scene in scenes:
        for condition, mutate in CONDITIONS.items():
            candidate = mutate(scene)
            rules_030 = sorted({i.rule_id for i in v030.validate(candidate).issues})
            rules_020 = sorted({i.rule_id for i in v020.validate(candidate).issues})
            expect_pass, expect_rules = EXPECT[condition]
            row = {
                "scene_id": scene["scene_id"],
                "condition": condition,
                "v030_rules": rules_030,
                "v020_blind_to_drift": condition.startswith("drift") and not rules_020,
                "pass": (not rules_030) == expect_pass and expect_rules <= set(rules_030),
            }
            rows.append(row)
            mark = "OK " if row["pass"] else "FAIL"
            print(f"{mark} {row['scene_id']:<42}{condition:<32} -> {rules_030}")

    report = {
        "validator_version": "0.3.0",
        "scenes": [s["scene_id"] for s in scenes],
        "conditions": list(CONDITIONS),
        "all_pass": all(r["pass"] for r in rows),
        "v020_blind_confirmed": all(
            r["v020_blind_to_drift"] for r in rows if r["condition"].startswith("drift")
        ),
        "rows": rows,
    }
    out = REPO / "generated" / "contract-v030" / "report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"all_pass={report['all_pass']} v020_blind_confirmed={report['v020_blind_confirmed']} -> {out}")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
