#!/usr/bin/env python3
"""R4c: legitimate-but-atypical normal samples must NOT be falsely rejected.

Takes the pristine passing pin_insertion scene and produces 8 variants that
are contract-compliant but unusual (extreme geometry, boundary tolerances,
axis variations, extra work zones/components). All should PASS validation.
Any critical issue on them is a false positive (false rejection).

Writes generated/normal-sample-fp/report.json
"""
import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from construction_scene_ready.validator import SceneValidator

BASE = REPO / "generated" / "local-pipeline" / "scenes" / "pin_insertion.json"
OUT = REPO / "generated" / "normal-sample-fp"
OUT.mkdir(parents=True, exist_ok=True)


def variants(scene):
    v = []

    # 1) 极端但合法的构件尺寸
    s = copy.deepcopy(scene)
    for c in s["components"]:
        if c["id"] == "steel_column":
            c["dimensions_m"] = [5.0, 0.4, 12.0]
        if c["id"] == "assembly_pin":
            c["dimensions_m"] = [0.03, 0.005, 0.005]
    v.append(("extreme_dimensions", s))

    # 2) 容差取合法边界值
    s = copy.deepcopy(scene)
    s["interfaces"][0]["tolerance_mm"] = 0.5
    v.append(("tolerance_small_legal", s))
    s = copy.deepcopy(scene)
    s["interfaces"][0]["tolerance_mm"] = 10.0
    v.append(("tolerance_large_legal", s))

    # 3) 孔轴取其它合法方向
    for ax, tag in [([0.0, -1.0, 0.0], "axis_neg_y"), ([0.0, 0.0, 1.0], "axis_pos_z")]:
        s = copy.deepcopy(scene)
        s["interfaces"][0]["axis"] = ax
        v.append((tag, s))

    # 4) 多一个合法工作区
    s = copy.deepcopy(scene)
    s["workzones"].append({"id": "zone_d", "active": False,
                           "payload": "workzones/zone_d_payload.usda",
                           "interaction_lod": "workzone"})
    v.append(("extra_workzone", s))

    # 5) 多一个引用闭合的合法构件
    s = copy.deepcopy(scene)
    extra = copy.deepcopy(s["components"][0])
    extra["id"] = "steel_brace_d"
    extra["ifc_guid"] = "steel_brace_d_guid_004"
    extra["name"] = "Diagonal brace D"
    extra["workzone_id"] = "zone_c"
    s["components"].append(extra)
    v.append(("extra_component", s))

    # 6) 构件在合法但非典型的位置
    s = copy.deepcopy(scene)
    for c in s["components"]:
        if c["id"] == "future_member_b":
            c["position_m"] = [8.0, 6.0, 3.0]
    v.append(("position_atypical", s))

    # 7) provenance 全部精确(边界: 零不确定区间)
    s = copy.deepcopy(scene)
    for p in s["provenance"]:
        p["confidence"] = 1.0
        p["uncertainty_interval"] = [p["value"], p["value"]]
    v.append(("provenance_exact", s))

    return v


def main():
    scene = json.loads(BASE.read_text())
    validator = SceneValidator()
    results = {}
    fp = 0
    for name, s in variants(scene):
        report = validator.validate(s)
        n_issues = len(report.issues)
        critical = [i for i in report.issues if getattr(i, "severity", "") == "critical"]
        results[name] = {"issues": n_issues, "critical": len(critical),
                         "messages": [getattr(i, "message", str(i)) for i in critical]}
        if critical:
            fp += 1
    out = {
        "base_scene": BASE.name,
        "n_variants": len(results),
        "false_positives": fp,
        "false_positive_rate": fp / len(results),
        "per_variant": results,
        "interpretation": "legitimate-but-atypical normal samples should all pass; any critical issue is a false rejection",
    }
    (OUT / "report.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
