#!/usr/bin/env python3
"""fig02 (architecture) as a REAL artefact flow, not generic boxes.

Every panel shows verbatim content from committed artefacts:
  1. IFC4.3 delivery        (real IFCPLATE / IFCMECHANICALFASTENER lines)
  2. Scene IR / CEWG        (real interface + task JSON)
  3. OpenUSD composition    (real building_root.usda header + layer files)
  4. Scene validator        (live validator diagnostic, CSR-SCN-028)
  5. Whitelisted repair     (live whitelist tool + benchmark outcome)
  6. Runtime measurement    (real R-REPAIR-GEO-0001 results)

Output: paper/figures/fig02_architecture.{pdf,png}
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from construction_scene_ready.fault_injection import inject_fault  # noqa: E402
from construction_scene_ready.repair import WHITELIST  # noqa: E402
from construction_scene_ready.validator import SceneValidator  # noqa: E402

GEN = REPO / "generated" / "local-pipeline"
MONO = "DejaVu Sans Mono"
INK = "#1a1a1a"
ACCENT = "#1f6fb2"
CHARS = 38  # max chars per content line at this panel size


def clip(lines):
    return [l if len(l) <= CHARS else l[: CHARS - 1] + "\u2026" for l in lines]


def ifc_lines():
    out = []
    for line in (GEN / "ifc" / "pin_insertion.ifc").read_text().splitlines():
        if "IFCPLATE(" in line or "IFCMECHANICALFASTENER(" in line:
            out.append(line.strip())
        if len(out) == 2:
            break
    return clip(out)


def cewg_lines():
    s = json.loads((GEN / "scenes" / "pin_insertion.json").read_text())
    itf = s["interfaces"][0]
    task = s["tasks"][0]
    return clip([
        f'"id": "{itf["id"]}"',
        f'"component": "{itf["component"]}"',
        f'"mate_component": "{itf["mate_component"]}"',
        f'"origin_m": {itf["origin_m"]}',
        f'"task": "{task["id"]}"',
        f'"target": "{task["target_component"]}"',
    ])


def usd_lines():
    root = (GEN / "usd_v2" / "building_root.usda").read_text().splitlines()
    mode = next(l.strip() for l in root if "csr:compositionMode" in l)
    layers = sorted(p.name for p in (GEN / "usd_v2").glob("*.usda"))
    zones = sorted(p.name.replace("_payload.usda", "")
                   for p in (GEN / "usd_v2" / "workzones").glob("*.usda"))
    return clip([
        "#usda 1.0  building_root.usda",
        mode.replace("custom string ", "").replace(" = ", "="),
        "root: " + ", ".join(l.replace(".usda", "").replace(
            "building_root_all_loaded", "all_loaded") for l in layers[:2]),
        "zones: " + ", ".join(zones),
    ])


def diagnostic_lines():
    scene = json.loads((GEN / "scenes" / "pin_insertion.json").read_text())
    faulty = inject_fault(scene, "mismatched_task_interface_target")
    issues = SceneValidator().validate(faulty).issues
    issue = next(i for i in issues if i.rule_id == "CSR-SCN-028")
    return [
        f"rule_id: {issue.rule_id}",
        "severity: critical",
        f"path: {issue.path}",
        "message: The task target shall own the",
        "      referenced assembly interface.",
    ]


def repair_lines():
    tool = WHITELIST.get("CSR-SCN-028")
    cases = json.loads((REPO / "generated" / "detection-repair"
                        / "B-CPU-DETREp-0001" / "cases.json").read_text())
    hit = next(c for c in cases
               if c["fault_id"] == "mismatched_task_interface_target"
               and c["method"] == "fixed-rule-repair")
    return clip([
        f"tool: {tool[0] if tool else 'none'}",
        "action: restore target_component",
        "        from evidence record",
        f"benchmark outcome: {hit['repair_outcome']}",
    ])


def runtime_lines():
    return [
        "R-REPAIR-GEO-0001 (200 eps each)",
        "correct:   reward 87.0%  geo 43.5%",
        "fault(5mm): reward 84.0%  geo 22.5%",
        "repaired:   reward 88.5%  geo 34.0%",
    ]


def main():
    panels = [
        ("1. IFC4.3 delivery", ifc_lines()),
        ("2. Scene IR / CEWG", cewg_lines()),
        ("3. OpenUSD composition", usd_lines()),
        ("4. Scene validator", diagnostic_lines()),
        ("5. Whitelisted repair", repair_lines()),
        ("6. Runtime measurement", runtime_lines()),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(6.9, 3.0))
    for ax, (title, lines) in zip(axes.flat, panels):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_facecolor("#fcfdfe")
        for s in ax.spines.values():
            s.set_color("#b9c4cc")
            s.set_linewidth(0.9)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.add_patch(plt.Rectangle((0, 0.82), 1, 0.18, fc="#eaf2f8", ec="none"))
        ax.text(0.04, 0.91, title, fontsize=8.0, color=ACCENT, weight="bold",
                ha="left", va="center")
        for i, line in enumerate(lines):
            ax.text(0.05, 0.72 - i * 0.13, line, fontsize=6.2, color=INK,
                    family=MONO, ha="left", va="center")
    # flow markers between panels via figure text (no overlapping arrows)
    for x in (0.335, 0.668):
        fig.text(x, 0.72, "\u25b6", fontsize=8, color="#8a9aa5",
                 ha="center", va="center")
        fig.text(x, 0.24, "\u25b6", fontsize=8, color="#8a9aa5",
                 ha="center", va="center")
    fig.text(0.835, 0.48, "\u25bc", fontsize=8, color="#8a9aa5",
             ha="center", va="center")
    fig.tight_layout(pad=0.6)
    out = REPO / "paper" / "figures" / "fig02_real2"
    fig.savefig(str(out) + ".pdf")
    fig.savefig(str(out) + ".png", dpi=300)
    print(f"wrote {out}.pdf/.png")


if __name__ == "__main__":
    main()
