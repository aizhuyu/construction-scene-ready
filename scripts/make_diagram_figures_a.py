#!/usr/bin/env python3
"""Generate schematic vector diagrams for Sections 1 and 4 (no manual numbers).

All content is taken from real repository artefacts:
  docs/fault-taxonomy.csv            (fault identifiers for Fig. 1 panel c)
  examples/minimal_scene.json        (IFC GUID, asset ids, provenance record)
  src/construction_scene_ready/cewg.py         (node/edge type vocabulary)
  src/construction_scene_ready/usd_compiler.py (USD layer names)
  src/construction_scene_ready/validator.py    (CSR-SCN rule count)
  src/construction_scene_ready/pipeline.py     (emitted artefact names)

Outputs: paper/figures/fig01_scene_gap.{pdf,png},
         paper/figures/fig02_architecture.{pdf,png},
         paper/figures/fig03_intermediate_representation.{pdf,png}
Style: Okabe-Ito colourblind-safe palette, min 6 pt text, PDF vector + 600 dpi PNG.
"""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Circle, Polygon

REPO = Path(__file__).resolve().parents[1]
FIGDIR = REPO / "paper" / "figures"

# Okabe-Ito palette
BLUE = "#0072B2"
ORANGE = "#D55E00"
GREEN = "#009E73"
YELLOW = "#E69F00"
SKY = "#56B4E9"
PINK = "#CC79A7"
GRAY = "#999999"
INK = "#1a1a1a"

plt.rcParams.update(
    {
        "font.size": 6.5,
        "font.family": "DejaVu Sans",
        "axes.linewidth": 0.6,
        "pdf.fonttype": 42,
    }
)


def load_fault_ids() -> list[str]:
    with (REPO / "docs" / "fault-taxonomy.csv").open(encoding="utf-8") as fh:
        return [row["fault_id"] for row in csv.DictReader(fh)]


def load_minimal_scene() -> dict:
    return json.loads((REPO / "examples" / "minimal_scene.json").read_text(encoding="utf-8"))


def rule_count() -> int:
    text = (REPO / "src" / "construction_scene_ready" / "validator.py").read_text(encoding="utf-8")
    return len(set(re.findall(r"CSR-SCN-\d{3}", text)))


def box(ax, xy, w, h, face, edge, text, fontsize=6.5, text_color="white",
        lw=0.9, rounding=0.02, weight="bold"):
    x, y = xy
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle=f"round,pad=0,rounding_size={rounding}",
            facecolor=face, edgecolor=edge, linewidth=lw, zorder=2,
        )
    )
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color=text_color, weight=weight, zorder=3)


def arrow(ax, p0, p1, color=INK, lw=0.9, style="-|>", mutation=8, ls="-"):
    ax.add_patch(
        FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=mutation,
                        color=color, linewidth=lw, linestyle=ls,
                        shrinkA=1, shrinkB=1, zorder=1)
    )


def panel_label(ax, label, x=0.02, y=0.96):
    ax.text(x, y, label, transform=ax.transAxes, ha="left", va="top",
            fontsize=7, weight="bold", color=INK)


def save(fig, name: str) -> None:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGDIR / f"{name}.pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(FIGDIR / f"{name}.png", dpi=600, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


# --------------------------------------------------------------------------
# Figure 1: asset readiness is not scene readiness (four linked panels)
# --------------------------------------------------------------------------
def fig01() -> None:
    scene = load_minimal_scene()
    guid = scene["components"][0]["ifc_guid"]
    faults = load_fault_ids()
    wanted = ["missing_workzone_payload", "wrong_up_axis",
              "unsupported_generated_friction"]
    picked = [f for f in wanted if f in faults]
    n_rules = rule_count()

    fig, axes = plt.subplots(1, 4, figsize=(7.5, 2.15))
    for ax in axes:
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

    # (a) IFC design model
    ax = axes[0]
    panel_label(ax, "(a) IFC design model")
    wall = FancyBboxPatch((0.10, 0.42), 0.80, 0.30, boxstyle="round,pad=0,rounding_size=0.02",
                          facecolor="#DDEBF5", edgecolor=BLUE, linewidth=0.9, zorder=2)
    ax.add_patch(wall)
    ax.text(0.50, 0.66, "IfcWall / IfcColumn", ha="center", fontsize=6, color=INK, zorder=3)
    for cx in (0.28, 0.52, 0.76):
        ax.add_patch(plt.Rectangle((cx - 0.075, 0.45), 0.15, 0.14,
                                   facecolor="white", edgecolor=BLUE, linewidth=0.7, zorder=3))
    ax.text(0.28, 0.52, "part", ha="center", va="center", fontsize=5.5, color=BLUE, zorder=4)
    ax.text(0.52, 0.52, "part", ha="center", va="center", fontsize=5.5, color=BLUE, zorder=4)
    ax.text(0.76, 0.52, "part", ha="center", va="center", fontsize=5.5, color=BLUE, zorder=4)
    ax.text(0.50, 0.30, "IFC GUID\n" + guid, ha="center", va="center",
            fontsize=5.5, color=INK, family="DejaVu Sans Mono")
    ax.text(0.50, 0.12, "design intent only", ha="center", fontsize=6,
            color=GRAY, style="italic")

    # (b) individually valid assets
    ax = axes[1]
    panel_label(ax, "(b) assets pass alone")
    items = [
        ("Robot\nunitree_g1", 0.72),
        ("Tool\ng1_parallel_gripper", 0.47),
        ("Component\nconnection_plate", 0.22),
    ]
    for label, yc in items:
        box(ax, (0.06, yc - 0.10), 0.68, 0.20, "#E4F2EC", GREEN, label,
            fontsize=6, text_color=INK, weight="normal")
        ax.text(0.84, yc, "\u2713", ha="center", va="center", fontsize=11,
                color=GREEN, weight="bold")
    ax.text(0.50, 0.05, "geometry, collision, mass OK", ha="center",
            fontsize=6, color=GRAY, style="italic")

    # (c) composed-scene defects
    ax = axes[2]
    panel_label(ax, "(c) composed scene fails")

    def wrap_fault(name: str, width: int = 18) -> str:
        parts, lines, cur = name.split("_"), [], ""
        for part in parts:
            cand = f"{cur}_{part}" if cur else part
            if len(cand) <= width:
                cur = cand
            else:
                lines.append(cur)
                cur = part
        lines.append(cur)
        return "\n".join(lines)

    for i, fault in enumerate(picked):
        yc = 0.74 - i * 0.26
        tri = Polygon([(0.08, yc - 0.07), (0.18, yc - 0.07), (0.13, yc + 0.06)],
                      closed=True, facecolor=YELLOW, edgecolor=ORANGE,
                      linewidth=0.9, zorder=3)
        ax.add_patch(tri)
        ax.text(0.13, yc - 0.035, "!", ha="center", va="center", fontsize=6.5,
                color=INK, weight="bold", zorder=4)
        ax.text(0.23, yc, wrap_fault(fault), ha="left", va="center",
                fontsize=5.8, color=ORANGE, family="DejaVu Sans Mono")
    ax.text(0.50, 0.03, "cross-asset faults (fault taxonomy)", ha="center",
            fontsize=6, color=GRAY, style="italic")

    # (d) scene contract check
    ax = axes[3]
    panel_label(ax, "(d) scene-level contract")
    shield = Polygon(
        [(0.30, 0.86), (0.70, 0.86), (0.70, 0.52), (0.50, 0.34), (0.30, 0.52)],
        closed=True, facecolor="#DCEEF9", edgecolor=BLUE, linewidth=1.0, zorder=2)
    ax.add_patch(shield)
    ax.text(0.50, 0.70, f"{n_rules} rules", ha="center", va="center",
            fontsize=7, color=BLUE, weight="bold", zorder=3)
    ax.text(0.50, 0.58, "CSR-SCN-001\u2013%03d" % n_rules, ha="center",
            va="center", fontsize=5.2, color=BLUE, zorder=3,
            family="DejaVu Sans Mono")
    for i, item in enumerate(["closed references", "provenance",
                              "task preconditions"]):
        y = 0.24 - i * 0.075
        ax.text(0.24, y, "\u2713", ha="center", va="center", fontsize=6.5,
                color=GREEN, weight="bold")
        ax.text(0.32, y, item, ha="left", va="center", fontsize=6, color=INK)

    # linking arrows between panels (adjust spacing first so positions are final)
    fig.subplots_adjust(wspace=0.12)
    fig.canvas.draw()
    for i in range(3):
        x0 = axes[i].get_position().x1
        x1 = axes[i + 1].get_position().x0
        ymid = (axes[i].get_position().y0 + axes[i].get_position().y1) / 2
        fig.add_artist(FancyArrowPatch((x0 + 0.004, ymid), (x1 - 0.004, ymid),
                                       transform=fig.transFigure,
                                       arrowstyle="-|>", mutation_scale=10,
                                       color=GRAY, linewidth=1.0))
    save(fig, "fig01_scene_gap")


# --------------------------------------------------------------------------
# Figure 2: six-stage architecture pipeline
# --------------------------------------------------------------------------
def fig02() -> None:
    n_rules = rule_count()

    stages = [
        ("Inputs", "IFC4.3 model\nTask contract\nRobot asset", SKY),
        ("Scene IR", "typed CEWG\nproperty graph", BLUE),
        ("USD layers", "global_navigation\nworkzone_payload\ninteraction", GREEN),
        ("Scene\nvalidator", f"{n_rules} deterministic\nrules CSR-SCN", BLUE),
        ("Whitelisted\nrepair", "rule\u2013tool map\nor human\nescalation", ORANGE),
        ("Reports +\nRTX runtime", "pass/fail report\nOmniverse task\nexecution", GRAY),
    ]
    artefacts = ["scene JSON\n+ IFC GUID map", "CEWG JSON", "USD layers",
                 "diagnostic JSON", "audit log"]

    fig, ax = plt.subplots(figsize=(7.5, 1.9))
    ax.set_xlim(0, 7.5)
    ax.set_ylim(0, 1.9)
    ax.axis("off")

    n = len(stages)
    bw, bh = 1.02, 1.02
    gap = (7.5 - n * bw) / (n + 1)
    y0 = 0.28
    for i, (title, body, color) in enumerate(stages):
        x = gap + i * (bw + gap)
        ax.add_patch(FancyBboxPatch((x, y0), bw, bh,
                                    boxstyle="round,pad=0,rounding_size=0.04",
                                    facecolor="white", edgecolor=color,
                                    linewidth=1.1, zorder=2))
        ax.add_patch(plt.Rectangle((x, y0 + bh - 0.24), bw, 0.24,
                                   facecolor=color, edgecolor="none", zorder=3))
        ax.text(x + bw / 2, y0 + bh - 0.12, title, ha="center", va="center",
                fontsize=6.5, color="white", weight="bold", zorder=4)
        ax.text(x + bw / 2, y0 + (bh - 0.24) / 2, body, ha="center", va="center",
                fontsize=5.8, color=INK, zorder=4)
        if i < n - 1:
            x0 = x + bw
            x1 = x + bw + gap
            arrow(ax, (x0 + 0.01, y0 + bh / 2), (x1 - 0.01, y0 + bh / 2),
                  color=INK, lw=1.0, mutation=9)
            ax.text((x0 + x1) / 2, y0 + bh + 0.30, artefacts[i], ha="center",
                    va="center", fontsize=5.4, color=INK, rotation=0,
                    family="DejaVu Sans Mono")

    # feedback edge: repair loops back to validator inputs
    x_rep = gap + 4 * (bw + gap) + bw / 2
    x_val = gap + 3 * (bw + gap) + bw / 2
    ax.add_patch(FancyArrowPatch((x_rep, y0), (x_val, y0),
                                 connectionstyle="arc3,rad=0.35",
                                 arrowstyle="-|>", mutation_scale=8,
                                 color=ORANGE, linewidth=0.8, linestyle="--",
                                 zorder=1))
    ax.text((x_rep + x_val) / 2, y0 - 0.20, "repaired scene JSON", ha="center",
            va="center", fontsize=5.4, color=ORANGE, family="DejaVu Sans Mono")

    ax.text(7.5 / 2, 1.82, "", ha="center")  # keep top margin stable
    save(fig, "fig02_architecture")


# --------------------------------------------------------------------------
# Figure 3: CEWG entity-relation diagram + provenance card
# --------------------------------------------------------------------------
def fig03() -> None:
    scene = load_minimal_scene()
    rec = next(r for r in scene["provenance"] if r["property"] == "mass_kg")

    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    ax.set_xlim(0, 7.5)
    ax.set_ylim(0, 4.4)
    ax.axis("off")

    # node positions (centres), sizes, colours, real attribute names
    nodes = {
        "WorkZone":          ((0.95, 3.55), (1.40, 0.62), YELLOW,
                              "active, payload,\ninteraction_lod"),
        "Component":         ((2.85, 2.75), (1.50, 0.62), BLUE,
                              "ifc_guid, mass_kg,\nconstruction_state"),
        "AssemblyInterface": ((4.95, 3.75), (1.70, 0.62), GREEN,
                              "axis, tolerance_mm,\ninterface type"),
        "ConstructionState": ((0.95, 1.35), (1.60, 0.62), PINK,
                              "state-machine node\n(name)"),
        "Task":              ((4.95, 2.10), (1.25, 0.62), BLUE,
                              "type, preconditions,\nsuccess_criteria"),
        "Robot":             ((6.80, 3.35), (1.00, 0.62), SKY,
                              "asset_uri,\ncapabilities"),
        "RobotCapability":   ((6.80, 2.30), (1.60, 0.62), GRAY,
                              "named capability\n(e.g. insertion)"),
        "Tool":              ((6.80, 1.25), (1.00, 0.62), SKY,
                              "asset_uri,\ncapabilities"),
        "ProvenanceRecord":  ((3.10, 0.62), (2.90, 1.05), ORANGE, ""),
    }

    def edge_pts(name):
        (cx, cy), (w, h), _, _ = nodes[name]
        return cx, cy, w, h

    def connect(a, b, label, color=INK, rad=0.0, off=0.16, ls="-",
                label_xy=None):
        ax_, ay, aw, ah = edge_pts(a)
        bx_, by, bw, bh = edge_pts(b)
        # clip to box borders
        dx, dy = bx_ - ax_, by - ay
        t_a = min((aw / 2) / abs(dx) if dx else 9, (ah / 2) / abs(dy) if dy else 9)
        t_b = min((bw / 2) / abs(dx) if dx else 9, (bh / 2) / abs(dy) if dy else 9)
        p0 = (ax_ + dx * t_a, ay + dy * t_a)
        p1 = (bx_ - dx * t_b, by - dy * t_b)
        ax.add_patch(FancyArrowPatch(p0, p1, connectionstyle=f"arc3,rad={rad}",
                                     arrowstyle="-|>", mutation_scale=7,
                                     color=color, linewidth=0.8, linestyle=ls,
                                     shrinkA=1, shrinkB=1, zorder=1))
        # label at the arc apex, offset perpendicular to the chord
        if label_xy is None:
            norm = math.hypot(dx, dy) or 1
            bump = off + abs(rad) * norm * 0.25
            mx = (p0[0] + p1[0]) / 2 - dy / norm * bump
            my = (p0[1] + p1[1]) / 2 + dx / norm * bump
        else:
            mx, my = label_xy
        ax.text(mx, my, label, ha="center", va="center", fontsize=5.2,
                color=color, family="DejaVu Sans Mono", zorder=3,
                bbox=dict(facecolor="white", edgecolor="none", pad=0.6, alpha=0.85))

    # draw nodes (except provenance card, drawn enlarged below)
    for name, ((cx, cy), (w, h), color, attrs) in nodes.items():
        if name == "ProvenanceRecord":
            continue
        ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                                    boxstyle="round,pad=0,rounding_size=0.05",
                                    facecolor="white", edgecolor=color,
                                    linewidth=1.1, zorder=2))
        ax.add_patch(plt.Rectangle((cx - w / 2, cy + h / 2 - 0.20), w, 0.20,
                                   facecolor=color, edgecolor="none", zorder=3))
        ax.text(cx, cy + h / 2 - 0.10, name, ha="center", va="center",
                fontsize=6.3, color="white", weight="bold", zorder=4)
        ax.text(cx, cy - 0.11, attrs, ha="center", va="center",
                fontsize=5.0, color=GRAY, family="DejaVu Sans Mono", zorder=4)

    # edges (real relation names from cewg.py)
    connect("Component", "WorkZone", "located_in")
    connect("Component", "ConstructionState", "has_state")
    connect("Component", "AssemblyInterface", "has_interface")
    connect("AssemblyInterface", "Component", "mates_with", rad=0.35, color=GREEN)
    connect("Task", "Robot", "performed_by")
    connect("Task", "Component", "targets")
    connect("Task", "AssemblyInterface", "uses_interface", off=-0.22)
    connect("Task", "Tool", "uses_tool", label_xy=(6.02, 1.42))
    connect("Robot", "RobotCapability", "has_capability", color=GRAY, off=0.30)
    connect("Tool", "RobotCapability", "provides_capability", color=GRAY, off=-0.34)
    connect("Task", "RobotCapability", "requires_capability", rad=-0.15,
            color=GRAY, ls="--", label_xy=(5.60, 1.60))

    # self loop: ConstructionState can_transition_to ConstructionState
    cx, cy, w, h = edge_pts("ConstructionState")
    ax.add_patch(FancyArrowPatch((cx - w / 2 + 0.15, cy - h / 2),
                                 (cx - w / 2 - 0.05, cy - h / 2 - 0.42),
                                 connectionstyle="arc3,rad=0.9",
                                 arrowstyle="-|>", mutation_scale=7,
                                 color=PINK, linewidth=0.8, zorder=1))
    ax.text(cx - 0.72, cy - h / 2 - 0.44, "can_transition_to", ha="center",
            fontsize=5.2, color=PINK, family="DejaVu Sans Mono")

    # provenance supports_property edge (to Component)
    connect("ProvenanceRecord", "Component", "supports_property", color=ORANGE,
            off=0.25)

    # enlarged provenance card (real record from examples/minimal_scene.json)
    (cx, cy), (w, h), color, _ = nodes["ProvenanceRecord"]
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                                boxstyle="round,pad=0,rounding_size=0.05",
                                facecolor="#FDF1E7", edgecolor=color,
                                linewidth=1.2, zorder=2))
    ax.add_patch(plt.Rectangle((cx - w / 2, cy + h / 2 - 0.22), w, 0.22,
                               facecolor=color, edgecolor="none", zorder=3))
    ax.text(cx, cy + h / 2 - 0.11, "ProvenanceRecord", ha="center", va="center",
            fontsize=6.3, color="white", weight="bold", zorder=4)
    lines = [
        f"entity: {rec['entity']}",
        f"property: {rec['property']}",
        f"value: {rec['value']} {rec['unit']}",
        f"source: {rec['source']}",
        f"confidence: {rec['confidence']}",
        "uncertainty_interval: "
        f"[{rec['uncertainty_interval'][0]}, {rec['uncertainty_interval'][1]}]",
    ]
    for i, line in enumerate(lines):
        ax.text(cx - w / 2 + 0.10, cy + h / 2 - 0.37 - i * 0.125, line,
                ha="left", va="center", fontsize=5.3, color=INK,
                family="DejaVu Sans Mono", zorder=4)

    save(fig, "fig03_intermediate_representation")


def main() -> None:
    fig01()
    fig02()
    fig03()
    print("wrote fig01_scene_gap, fig02_architecture, fig03_intermediate_representation")


if __name__ == "__main__":
    main()
