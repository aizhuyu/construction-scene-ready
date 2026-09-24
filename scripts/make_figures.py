#!/usr/bin/env python3
"""Generate paper figures from registered result files (no manual numbers).

Inputs (all registered/committed artefacts):
  data/results/detection_repair.csv      (B0/B1/ablations, deterministic)
  data/results/detection_repair_llm.csv  (B2/B3/A5 agent episodes)
  data/results/resource_efficiency.csv   (A3 composition resource rows)
  data/results/task_outcomes.csv         (humanoid episodes, failure causes)
  generated/readiness-task-link/report.json (validator readiness per condition)

Outputs: paper/figures/fig07_detection_repair.{pdf,png},
         paper/figures/fig08_efficiency_task.{pdf,png}
Style: colourblind-safe palette + hatch (redundant encoding), PDF vector.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
FIGDIR = REPO / "paper" / "figures"

# colourblind-safe (Okabe–Ito) + hatch for grayscale redundancy
C = {"valid": "#009E73", "incorrect": "#D55E00", "escalated": "#E69F00",
     "failed": "#CC79A7", "not_attempted": "#999999"}
H = {"valid": "", "incorrect": "//", "escalated": "..", "failed": "xx",
     "not_attempted": "\\\\"}

METHOD_LABEL = {
    "direct-conversion": "B0 direct",
    "fixed-rule-repair": "B1 fixed-rule",
    "unconstrained-agent": "B2 free-form",
    "validator-grounded-agent": "B3 grounded",
}
OUTCOMES = ("valid", "incorrect", "escalated", "failed", "not_attempted")


def load_csv(name):
    return list(csv.DictReader((REPO / "data" / "results" / name).open(encoding="utf-8")))


def fig07():
    det = load_csv("detection_repair.csv")
    llm = load_csv("detection_repair_llm.csv")
    rows = det + llm
    methods = [m for m in METHOD_LABEL if any(r["method"] == m for r in rows)]
    # (a) 仅含产生 typed findings 的方法; 自由 agent 无检测输出(n/a), 不画成 0
    det_methods = [m for m in methods if m != "unconstrained-agent"]

    fig, axes = plt.subplots(1, 2, figsize=(7.5, 2.9))
    # (a) detection: critical-fault case-level detection rate per method
    ax = axes[0]
    for i, m in enumerate(det_methods):
        sub = [r for r in rows if r["method"] == m]
        det_flags = [int(r["critical_detected"]) for r in sub]
        rate = np.mean(det_flags)
        ax.bar(i, rate, color="#0072B2", edgecolor="black", linewidth=0.5)
        ax.text(i, rate + 0.02, f"{rate * 100:.0f}%", ha="center", fontsize=7)
    ax.set_xticks(range(len(det_methods)))
    ax.set_xticklabels([METHOD_LABEL[m] for m in det_methods], fontsize=7, rotation=12)
    ax.set_ylabel("critical-fault detection", fontsize=7)
    ax.set_ylim(0, 1.12)
    ax.set_title("(a) detection (case level)", fontsize=8)
    ax.tick_params(labelsize=6)

    # (b) repair outcome composition per method
    ax = axes[1]
    bottoms = np.zeros(len(methods))
    for outcome in OUTCOMES:
        vals = []
        for m in methods:
            sub = [r for r in rows if r["method"] == m]
            vals.append(np.mean([r["repair_outcome"] == outcome for r in sub]))
        ax.bar(range(len(methods)), vals, bottom=bottoms, color=C[outcome],
               hatch=H[outcome], edgecolor="black", linewidth=0.4,
               label=outcome.replace("_", " "))
        bottoms += np.array(vals)
    ax.set_xticks(range(len(methods)))
    ax.set_xticklabels([METHOD_LABEL[m] for m in methods], fontsize=7, rotation=12)
    ax.set_ylabel("episode proportion", fontsize=7)
    ax.set_title("(b) repair outcomes", fontsize=8)
    ax.legend(fontsize=6, loc="lower left", framealpha=0.9)
    ax.tick_params(labelsize=6)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(FIGDIR / f"fig07_detection_repair.{ext}", dpi=600)
    plt.close(fig)


def fig08():
    res = [r for r in load_csv("resource_efficiency.csv")
           if not r["scenario"].startswith("scale_")]  # 只画三个基准场景
    task = load_csv("task_outcomes.csv")
    report = json.loads((REPO / "generated" / "readiness-task-link" / "report.json").read_text())

    fig, axes = plt.subplots(1, 3, figsize=(7.5, 2.6))
    # (a) composition resource: paired prims + layer bytes per scene
    ax = axes[0]
    scenes = sorted({r["scenario"] for r in res})
    short = {"connection_plate_positioning": "plate", "pin_insertion": "pin",
             "sequential_assembly": "seq"}
    x = np.arange(len(scenes))
    ta = {r["scenario"]: r for r in res if r["layer_condition"] == "task_activated"}
    al = {r["scenario"]: r for r in res if r["layer_condition"] == "all_loaded"}
    ax.plot(x - 0.05, [int(al[s]["active_prims"]) for s in scenes], "s",
            color="#D55E00", label="all loaded", markersize=5)
    ax.plot(x + 0.05, [int(ta[s]["active_prims"]) for s in scenes], "o",
            color="#0072B2", label="task activated", markersize=5)
    for i, s in enumerate(scenes):
        ax.plot([i - 0.05, i + 0.05],
                [int(al[s]["active_prims"]), int(ta[s]["active_prims"])],
                color="gray", linewidth=0.7, zorder=0)
    ax.set_xticks(x)
    ax.set_xticklabels([short.get(s, s) for s in scenes], fontsize=7)
    ax.set_ylabel("active prims", fontsize=7)
    ax.set_title("(a) task-activated composition", fontsize=8)
    ax.legend(fontsize=6)
    ax.tick_params(labelsize=6)

    # (b) readiness vs humanoid success (condition level): reward and the
    # simultaneous geometric-valid criterion, one point per condition each
    ax = axes[1]
    stats = report["condition_stats"]
    LABEL = {
        "geometry_2mm": "hole 2mm", "geometry_5mm": "hole 5mm",
        "geometry_10mm": "hole 10mm", "geometry_member_10mm": "member 10mm",
        "interface_0.75mm": "clear .75", "interface_0.5mm": "clear .5",
        "interface_0.25mm": "clear .25", "physics_half": "mass .5/2x",
    }
    # absolute label y-positions (data coords) at x=1.0, staggered to avoid
    # collisions in the geometric-valid column
    LABEL_Y = {
        "physics_half": 52.0, "geometry_member_10mm": 45.5,
        "geometry_2mm": 39.0, "geometry_5mm": 32.5,
        "interface_0.75mm": 25.5, "interface_0.5mm": 19.0,
        "interface_0.25mm": 11.0, "geometry_10mm": 4.0,
    }
    for cond, readiness in report["readiness"].items():
        if cond == "none" or cond not in stats:
            continue
        seed_stats = [st for k, st in stats[cond].items() if str(k).isdigit()]
        rate = float(np.mean([st["success_rate"] for st in seed_stats]))
        geo = float(np.mean([st.get("geo_rate", np.nan) for st in seed_stats]))
        flagged = readiness < 1.0
        color = "#D55E00" if flagged else "#0072B2"
        marker = "s" if flagged else "o"
        ax.scatter(readiness, rate * 100, marker=marker, color=color,
                   edgecolor="black", linewidth=0.4, s=26, zorder=3)
        if not np.isnan(geo):
            ax.scatter(readiness, geo * 100, marker=marker, color="white",
                       edgecolor=color, linewidth=1.0, s=26, zorder=3)
            ax.plot([readiness, readiness], [geo * 100, rate * 100],
                    color=color, linewidth=0.6, zorder=2)
        if cond in LABEL and not np.isnan(geo):
            y = LABEL_Y[cond]
            ax.annotate(LABEL[cond], (readiness, geo * 100),
                        xytext=(1.0, y), fontsize=4.5, ha="right",
                        va="center", color=color, zorder=4,
                        arrowprops=dict(arrowstyle="-", color=color,
                                        linewidth=0.4))
    # the three fatal flagged conditions share one point; label them inside
    # the empty middle band between the two readiness clusters
    ax.annotate("semantic missing", (0.9667, 12.5), xytext=(0.969, 15.0),
                fontsize=4.5, ha="left", va="center", color="#D55E00",
                zorder=4, arrowprops=dict(arrowstyle="-", color="#D55E00",
                                          linewidth=0.4))
    ax.annotate("semantic wrong /\ntask ref / state (0)", (0.9667, 0.5),
                xytext=(0.969, 5.0), fontsize=4.5, ha="left", va="center",
                color="#D55E00", zorder=4,
                arrowprops=dict(arrowstyle="-", color="#D55E00",
                                linewidth=0.4))
    ax.set_xlabel("validator readiness score", fontsize=7)
    ax.set_ylabel("insertion success (%)", fontsize=7)
    ax.set_title("(b) readiness vs task success", fontsize=8)
    ax.scatter([], [], marker="s", color="#D55E00", label="flagged by validator")
    ax.scatter([], [], marker="o", color="#0072B2", label="passes contract")
    ax.scatter([], [], marker="o", color="gray", edgecolor="black",
               linewidth=0.4, label="reward success")
    ax.scatter([], [], marker="o", color="white", edgecolor="gray",
               linewidth=1.0, label="geometric-valid")
    ax.legend(fontsize=5.5, loc="upper left")
    ax.tick_params(labelsize=6)

    # (c) failure-cause composition across defect conditions
    ax = axes[2]
    causes = {}
    for r in task:
        if r["failure_cause"]:
            key = r["case_id"].split("__s")[0]
            causes.setdefault(key, {"misalignment": 0, "insufficient_depth": 0})
            causes[key][r["failure_cause"]] += 1
    conds = [c for c in report["readiness"] if c != "none" and c in causes]
    y = np.arange(len(conds))
    left = np.zeros(len(conds))
    for cause, color, hatch in (("misalignment", "#E69F00", ".."),
                                ("insufficient_depth", "#56B4E9", "//")):
        vals = np.array([causes[c][cause] for c in conds], dtype=float)
        totals = np.array([sum(causes[c].values()) for c in conds])
        frac = np.divide(vals, totals, out=np.zeros_like(vals), where=totals > 0)
        ax.barh(y, frac, left=left, color=color, hatch=hatch,
                edgecolor="black", linewidth=0.4, label=cause.replace("_", " "))
        left += frac
    ax.set_yticks(y)
    ax.set_yticklabels(conds, fontsize=5)
    ax.set_xlabel("share of failed episodes", fontsize=7)
    ax.set_title("(c) failure causes", fontsize=8)
    ax.legend(fontsize=6)
    ax.tick_params(labelsize=6)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(FIGDIR / f"fig08_efficiency_task.{ext}", dpi=600)
    plt.close(fig)


def main() -> int:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    fig07()
    fig08()
    print("wrote fig07_detection_repair.{pdf,png}, fig08_efficiency_task.{pdf,png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
