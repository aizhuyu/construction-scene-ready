#!/usr/bin/env python3
"""Programmatic vector diagrams for ConstructionSceneReady (figures 4-6).

Every panel renders TRUE committed artefacts:

* fig04_multiscale_composition -- the real OpenUSD composition tree of
  ``generated/local-pipeline/usd/pin_insertion/building_root.usda``
  (task_activated mode) plus a measured inset of active prims from
  ``data/results/resource_efficiency.csv``.
* fig05_repair_loop -- the six contract families of
  ``docs/scene-readiness-rules.csv`` / the contract table, a genuine
  CSR-SCN-023 diagnostic produced by running ``SceneValidator`` on an
  injected ``unsupported_generated_friction`` fault, and the
  Compile->Validate->Diagnose->Select tool->Repair->Revalidate->
  Pass/Escalate state machine with the real whitelisted tool
  ``restore_scene_units`` (repair.WHITELIST).
* fig06_benchmark -- scenario names, embodiment levels, frozen fault
  partitions and the taxonomy sha256 read from
  ``data/partition-manifest.json``, and the B0-B3 method identifiers from
  ``docs/experiment-registry.csv``.

Style: Okabe-Ito colour-blind-safe palette, minimum 6 pt text,
PDF (vector) + PNG (600 dpi), 7.5 in wide for ``figure*``.

Output: paper/figures/fig04_multiscale_composition.{pdf,png}
        paper/figures/fig05_repair_loop.{pdf,png}
        paper/figures/fig06_benchmark.{pdf,png}
"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from construction_scene_ready.fault_injection import inject_fault  # noqa: E402
from construction_scene_ready.repair import WHITELIST  # noqa: E402
from construction_scene_ready.suites import build_scenes  # noqa: E402
from construction_scene_ready.validator import SceneValidator  # noqa: E402

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
        "font.family": "DejaVu Sans",
        "font.size": 7,
        "pdf.fonttype": 42,
        "axes.edgecolor": INK,
    }
)

MONO = {"family": "DejaVu Sans Mono"}


def box(ax, cx, cy, w, h, title, body, color, *, dashed=False, title_fs=7.0,
        body_fs=6.2, fill_alpha=0.14, mono_body=True,
        lw=1.2, body_color=INK):
    """Rounded box with a bold title line and wrapped body lines."""
    patch = FancyBboxPatch(
        (cx - w / 2, cy - h / 2), w, h,
        boxstyle="round,pad=0.4,rounding_size=0.8",
        linewidth=lw, edgecolor=color,
        facecolor=color, alpha=fill_alpha,
        linestyle="--" if dashed else "-",
        mutation_aspect=1.0,
    )
    ax.add_patch(patch)
    # border drawn on top at full alpha so colours stay saturated
    border = FancyBboxPatch(
        (cx - w / 2, cy - h / 2), w, h,
        boxstyle="round,pad=0.4,rounding_size=0.8",
        linewidth=lw, edgecolor=color, facecolor="none",
        linestyle="--" if dashed else "-",
    )
    ax.add_patch(border)
    ax.text(cx, cy + h / 2 - 2.4, title, ha="center", va="top",
            fontsize=title_fs, fontweight="bold", color=INK, **MONO)
    y = cy + h / 2 - 5.6
    for line in body:
        ax.text(cx, y, line, ha="center", va="top", fontsize=body_fs,
                color=body_color, **(MONO if mono_body else {}))
        y -= 3.1
    return patch


def edge(ax, x1, y1, x2, y2, color, *, dashed=False, label=None,
         label_dx=0.0, label_dy=0.0, rad=0.0, lw=1.1):
    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=7,
        linewidth=lw, color=color,
        linestyle="--" if dashed else "-",
        connectionstyle=f"arc3,rad={rad}",
        shrinkA=1, shrinkB=1,
    )
    ax.add_patch(arrow)
    if label:
        ax.text((x1 + x2) / 2 + label_dx, (y1 + y2) / 2 + label_dy, label,
                ha="center", va="center", fontsize=6.0, color=color,
                style="italic")


def save(fig, name: str) -> None:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGDIR / f"{name}.pdf")
    fig.savefig(FIGDIR / f"{name}.png", dpi=600)
    plt.close(fig)
    print(f"wrote {FIGDIR / name}.pdf/.png")


# ---------------------------------------------------------------- fig04 ----

def fig04() -> None:
    rows = list(csv.DictReader(
        (REPO / "data" / "results" / "resource_efficiency.csv").open()))
    # the CSV also carries scale-sweep rows from run_scale_resource.py;
    # the inset reports the three benchmark scenarios only
    keep = {"connection_plate_positioning", "pin_insertion",
            "sequential_assembly"}
    rows = [r for r in rows if r["scenario"] in keep]
    scenarios = []
    for row in rows:
        if row["scenario"] not in scenarios:
            scenarios.append(row["scenario"])
    vals = {s: {} for s in scenarios}
    for row in rows:
        vals[row["scenario"]][row["layer_condition"]] = int(row["active_prims"])

    fig = plt.figure(figsize=(7.5, 3.45))
    ax = fig.add_axes([0.005, 0.0, 0.635, 1.0])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(1, 98.5, "OpenUSD composition tree — pin_insertion "
            "(task_activated mode)", fontsize=7.4, fontweight="bold",
            color=INK, va="top")

    # root
    box(ax, 47, 85.5, 66, 14, "building_root.usda",
        ['def Xform "World"', 'csr:compositionMode = "task_activated"'],
        BLUE, title_fs=7.4)
    # children
    box(ax, 16, 54, 30, 22, 'def "Global"',
        ["prepend references =", "@./global_navigation.usda@"],
        SKY)
    box(ax, 50, 54, 30, 22, 'def Xform "WorkZones"',
        ['def "zone_a"  (active zone)', "prepend payload =",
         "@./workzones/", "zone_a_payload.usda@"],
        ORANGE, dashed=True)
    box(ax, 84, 54, 30, 22, 'def Xform "Tasks"',
        ['def "insert_pin"', "prepend references =",
         "@./interaction/", "insert_pin.usda@"],
        GREEN)

    edge(ax, 38, 78.4, 18, 65.6, SKY, label="reference", label_dx=-4, label_dy=1.5)
    edge(ax, 47, 78.4, 50, 65.6, ORANGE, dashed=True, label="payload",
         label_dx=7.5, label_dy=1.5)
    edge(ax, 57, 78.4, 82, 65.6, GREEN, label="reference", label_dx=2, label_dy=1.5)

    ax.text(49, 37.2, "payload arc: loadable / unloadable per work zone",
            ha="center", fontsize=6.0, color=ORANGE, style="italic")

    # un-composed sibling payloads
    box(ax, 33, 24, 34, 13, "zone_b_payload.usda",
        ["declared in package,", "not composed"], GRAY, dashed=True, lw=1.0)
    box(ax, 72, 24, 34, 13, "zone_c_payload.usda",
        ["declared in package,", "not composed"], GRAY, dashed=True, lw=1.0)
    ax.text(52.5, 13.5,
            "sibling zone payloads are composed only by "
            "building_root_all_loaded.usda;\nbuilding_root.usda "
            "(task_activated) composes the active zone alone",
            ha="center", va="top", fontsize=6.0, color=GRAY)

    # measured inset
    axi = fig.add_axes([0.685, 0.13, 0.30, 0.60])
    width = 0.38
    xs = range(len(scenarios))
    for i, s in enumerate(scenarios):
        axi.bar(i - width / 2, vals[s]["task_activated"], width,
                color=BLUE, label="task_activated" if i == 0 else None)
        axi.bar(i + width / 2, vals[s]["all_loaded"], width,
                color=ORANGE, label="all_loaded" if i == 0 else None)
        axi.text(i - width / 2, vals[s]["task_activated"] + 0.4,
                 str(vals[s]["task_activated"]), ha="center", fontsize=6.2,
                 color=BLUE, fontweight="bold")
        axi.text(i + width / 2, vals[s]["all_loaded"] + 0.4,
                 str(vals[s]["all_loaded"]), ha="center", fontsize=6.2,
                 color=ORANGE, fontweight="bold")
    short = {"connection_plate_positioning": "connection\nplate",
             "pin_insertion": "pin\ninsertion",
             "sequential_assembly": "sequential\nassembly"}
    axi.set_xticks(list(xs))
    axi.set_xticklabels([short.get(s, s) for s in scenarios], fontsize=6.2)
    axi.set_ylabel("active prims", fontsize=6.5)
    axi.set_title("Measured working set\n(data/results/resource_efficiency.csv)",
                  fontsize=6.8)
    axi.tick_params(axis="y", labelsize=6.2)
    axi.set_ylim(0, max(v["all_loaded"] for v in vals.values()) + 6)
    axi.legend(fontsize=6.2, frameon=False, loc="upper left")
    for spine in ("top", "right"):
        axi.spines[spine].set_visible(False)

    save(fig, "fig04_multiscale_composition")


# ---------------------------------------------------------------- fig05 ----

def _real_csr_scn_023():
    """Run the validator on the true injected fault and return its record."""
    with tempfile.TemporaryDirectory() as tmp:
        scenes = build_scenes("variant", 1, Path(tmp))
    scene = next(s for s in scenes if s["scene_id"].startswith("pin_insertion"))
    faulty = inject_fault(scene, "unsupported_generated_friction")
    issues = SceneValidator().validate(faulty).issues
    issue = next(i for i in issues if i.rule_id == "CSR-SCN-023")
    record = next(r for r in faulty["provenance"]
                  if r.get("source_type") == "unverified_model_generation")
    return issue, record


def fig05() -> None:
    issue, record = _real_csr_scn_023()
    whitelisted = WHITELIST.get(issue.rule_id)
    permitted = whitelisted[0] if whitelisted else None

    fig = plt.figure(figsize=(7.5, 3.55))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    # ---------------- left: contract families ----------------
    ax.text(1, 98, "Contract families", fontsize=7.2,
            fontweight="bold", va="top")
    ax.text(1, 94.5, "(docs/scene-readiness-rules.csv)", fontsize=6.0,
            color=GRAY, va="top", style="italic")
    families = [
        ("Identity & closure", ["e.g. CSR-SCN-003/004"], BLUE),
        ("Spatial consistency",
         ["e.g. CSR-SCN-001/002", "CSR-SCN-022"], SKY),
        ("Assembly interface",
         ["e.g. CSR-SCN-012–014", "CSR-SCN-018–020"], GREEN),
        ("Construction state",
         ["e.g. CSR-SCN-009/010", "CSR-SCN-021"], YELLOW),
        ("Physics & stability", ["e.g. CSR-SCN-017"], PINK),
        ("Provenance & fidelity",
         ["e.g. CSR-SCN-015/016", "CSR-SCN-023/030"], ORANGE),
    ]
    fx = [8.6, 24.2]
    fy = [77, 51.5, 26]
    for k, (name, rules, color) in enumerate(families):
        box(ax, fx[k % 2], fy[k // 2], 14.4, 20.5, name, rules, color,
            title_fs=6.0, body_fs=6.0, mono_body=True)
    ax.text(16.4, 9.5, "30 deterministic rules; every violation emits a\n"
            "typed, machine-readable diagnostic",
            ha="center", va="top", fontsize=6.0, color=GRAY, style="italic")

    # ---------------- centre: diagnostic record ----------------
    ax.text(34.5, 98, "Diagnostic record (true validator output)",
            fontsize=7.2, fontweight="bold", va="top")
    card = FancyBboxPatch((34.5, 6), 27, 86,
                          boxstyle="round,pad=0.4,rounding_size=0.8",
                          linewidth=1.2, edgecolor=INK,
                          facecolor=INK, alpha=0.05)
    ax.add_patch(card)
    ax.add_patch(FancyBboxPatch((34.5, 6), 27, 86,
                                boxstyle="round,pad=0.4,rounding_size=0.8",
                                linewidth=1.2, edgecolor=INK,
                                facecolor="none"))
    lines = [
        ("rule_id", issue.rule_id),
        ("family", "provenance"),
        ("severity", issue.severity),
        ("path", issue.path),
        ("evidence", f'source_type = "{record["source_type"]}"'),
        ("message", issue.message),
        ("permitted tools", permitted or "none — not in WHITELIST"),
        ("policy", "escalate; no automatic repair"),
    ]
    y = 88.5
    for key, value in lines:
        ax.text(36, y, key, fontsize=6.4, fontweight="bold", color=BLUE,
                va="top")
        wrapped = textwrap.wrap(value, width=34) or [""]
        ax.text(36, y - 3.3, "\n".join(wrapped), fontsize=6.2, va="top",
                **MONO)
        y -= 3.3 + 3.0 * len(wrapped) + 1.6

    # ---------------- right: state machine ----------------
    ax.text(67, 98, "Repair state machine", fontsize=7.2,
            fontweight="bold", va="top")
    sm_x, sm_w, sm_h = 75.5, 17, 6.6
    states = [
        ("Compile", GRAY, 89),
        ("Validate", BLUE, 78.5),
        ("Diagnose", SKY, 68),
        ("Select tool", YELLOW, 57.5),
        ("Repair", GREEN, 47),
        ("Revalidate", BLUE, 36.5),
    ]
    for name, color, cy in states:
        box(ax, sm_x, cy, sm_w, sm_h, name, [], color, title_fs=6.4,
            lw=1.1)
    for a, b in zip(states, states[1:]):
        edge(ax, sm_x, a[2] - sm_h / 2 - 0.6, sm_x, b[2] + sm_h / 2 + 0.6,
             INK, lw=0.9)

    box(ax, 69.5, 22, 14, 6.6, "Pass", [], GREEN, title_fs=6.8, lw=1.4)
    box(ax, 89.5, 22, 16, 6.6, "Escalate", [], ORANGE, title_fs=6.8,
        lw=1.4)
    edge(ax, sm_x - 3, 33.1, 69.5, 25.7, GREEN, lw=0.9, label="clean",
         label_dx=-3.2, label_dy=0.6)
    edge(ax, sm_x + 3, 33.1, 89.5, 25.7, ORANGE, lw=0.9, label="no permitted\ntool",
         label_dx=6.4, label_dy=1.2)

    # loop back: issues remain
    loop = FancyArrowPatch((sm_x - sm_w / 2 - 0.6, 36.5),
                           (sm_x - sm_w / 2 - 0.6, 68),
                           arrowstyle="-|>", mutation_scale=7,
                           linewidth=0.9, color=INK, linestyle=":",
                           connectionstyle="arc3,rad=0.55")
    ax.add_patch(loop)
    ax.text(62.4, 52.5, "issues\nremain", fontsize=6.0, rotation=90,
            ha="center", va="center", color=INK, style="italic")

    ax.text(84.5, 47, "bounded whitelisted\ntool, e.g.\nCSR-SCN-002 →\n"
            "restore_scene_units", fontsize=6.0, ha="left", va="center",
            color=GREEN, **MONO)
    ax.text(89.5, 13.2, "e.g. CSR-SCN-023\nunsupported_generated_\nfriction",
            fontsize=6.0, ha="center", va="top", color=ORANGE, **MONO)

    save(fig, "fig05_repair_loop")


# ---------------------------------------------------------------- fig06 ----

def fig06() -> None:
    manifest = json.loads(
        (REPO / "data" / "partition-manifest.json").read_text())
    parts = manifest["partitions"]
    n_dev = len(parts["development"]["faults"])
    n_test = len(parts["test"]["faults"])
    n_chal = len(parts["challenge"]["faults"])
    sha8 = manifest["taxonomy_sha256"][:8]

    fig = plt.figure(figsize=(7.5, 3.8))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    cx3 = [17, 50, 83]

    # ---- row 1: scenarios ----
    ax.text(1, 98, "Scenarios (generated IFC fixtures → OpenUSD stages)",
            fontsize=7.2, fontweight="bold", va="top")
    scenarios = ["connection_plate_positioning", "pin_insertion",
                 "sequential_assembly"]
    for cx, name in zip(cx3, scenarios):
        box(ax, cx, 85, 29, 13, name,
            ["base scene + fault-injected variants"], BLUE, title_fs=6.8)

    # ---- row 2: embodiment levels ----
    ax.text(1, 70.5, "Embodiment levels (progression gated by stop criteria)",
            fontsize=7.2, fontweight="bold", va="top")
    levels = ["Level 1\nfixed base", "Level 2\nwhole body (in-place)",
              "Level 3\nmobile manipulation\n(building-scale)"]
    for cx, name in zip(cx3, levels):
        lines = name.split("\n")
        box(ax, cx, 57, 29, 12.5, lines[0], lines[1:], GREEN, title_fs=6.6,
            mono_body=False)
    for x1, x2 in ((31.5, 35.5), (64.5, 68.5)):
        edge(ax, x1, 57, x2, 57, INK, lw=0.9)
    ax.text(50, 48.8, "a level is attempted only when the preceding level "
            "satisfies the stop criteria", ha="center", va="top",
            fontsize=6.0, color=GRAY, style="italic")

    # ---- row 3: partitions / methods / freeze ----
    ax.text(1, 42.5, "Fault partitions · comparison methods · freeze",
            fontsize=7.2, fontweight="bold", va="top")
    box(ax, 17, 21, 30, 30, "Fault partitions (frozen)",
        [f"development   {n_dev}  (base scenes)",
         f"test         {n_test}  (variants)",
         f"challenge     {n_chal}  (variants)",
         "held out; escalation",
         "expected (e.g. CSR-SCN-023)",
         f"total {n_dev + n_test + n_chal} = 30 single",
         "+ 5 compound faults"],
        SKY, title_fs=6.6, body_fs=6.0)
    box(ax, 50, 21, 30, 30, "Methods",
        ["B0  direct-conversion",
         "B1  fixed-rule-repair",
         "B2  unconstrained-agent",
         "B3  validator-grounded agent",
         "",
         "identical scene + fault;",
         "no access to the pristine",
         "target or the fault label"],
        GREEN, title_fs=6.6, body_fs=6.0)
    box(ax, 83, 21, 30, 30, "Frozen before comparison",
        ["partition-manifest.json",
         f"version {manifest['manifest_version']}",
         "taxonomy_sha256",
         f"{sha8}…",
         "",
         "partition counts are read",
         "from the frozen manifest,",
         "not entered manually"],
        ORANGE, title_fs=6.6, body_fs=6.0)

    save(fig, "fig06_benchmark")


def main() -> int:
    fig04()
    fig05()
    fig06()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
