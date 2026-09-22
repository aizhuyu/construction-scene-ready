#!/usr/bin/env python3
"""Compose Figure 1 (scene gap) with REAL simulator renders.

(a) IFC design model -> OpenUSD scene   (structure + robot, real render)
(b) individual assets validate OK       (robot / tool / component, real renders + green check)
(c) composed task scene fails           (bolt blocked at plate, real render + red cross)
(d) scene-level contract catches it     (validator report panel, rule list)

Layout: horizontal flow, uniform panel heights, journal-clean.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from PIL import Image

FR = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/fig1_frames4")
STRUCT = os.path.expanduser(sys.argv[2] if len(sys.argv) > 2 else "~/fig_structure2/fig7_structure.png")
OUT_PDF = sys.argv[3] if len(sys.argv) > 3 else "fig01_scene_gap.pdf"
OUT_PNG = os.path.splitext(OUT_PDF)[0] + ".png"

GREEN = "#1a9e4b"
RED = "#d23c3c"
BLUE = "#1f6fb2"


def load(path):
    return Image.open(path)


def badge(ax, symbol, color, x=0.93, y=0.90):
    ax.text(x, y, symbol, transform=ax.transAxes, fontsize=15, color="white",
            ha="center", va="center", fontweight="bold", zorder=8,
            bbox=dict(boxstyle="circle,pad=0.28", fc=color, ec="white", lw=1.2))


def panel(ax, img, title):
    ax.imshow(img)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(True)
        s.set_color("#cccccc")
        s.set_linewidth(0.8)
    ax.set_title(title, fontsize=8.0, loc="left", pad=2)


def arrow(fig, x0, x1, y):
    fig.patches.append(mpatches.FancyArrowPatch(
        (x0, y), (x1, y), transform=fig.transFigure,
        arrowstyle="-|>", mutation_scale=16, color="#888888", lw=1.6, zorder=9))


def main():
    fig = plt.figure(figsize=(7.4, 2.9))

    # (a) 设计模型->场景
    ax_a = fig.add_axes([0.015, 0.16, 0.24, 0.70])
    panel(ax_a, load(STRUCT), "(a) IFC design model\n-> OpenUSD scene")

    # (b) 三个资产各自通过
    ax_b = fig.add_axes([0.315, 0.16, 0.24, 0.70])
    ax_b.axis("off")
    ax_b.set_title("(b) assets validate alone", fontsize=8.0, loc="left", pad=2)
    for i, (imgname, lab) in enumerate([("fig1_b1_robot.png", "robot"),
                                        ("fig1_b2_tool.png", "tool"),
                                        ("fig1_b3_component.png", "component")]):
        sub = ax_b.inset_axes([0.0, 0.62 - i * 0.33, 0.62, 0.30])
        sub.imshow(load(os.path.join(FR, imgname)))
        sub.set_xticks([]); sub.set_yticks([])
        for s in sub.spines.values():
            s.set_visible(True); s.set_color("#cccccc"); s.set_linewidth(0.7)
        badge(sub, "\u2713", GREEN, x=0.88, y=0.80)
        ax_b.text(0.65, 0.62 - i * 0.33 + 0.15, lab, fontsize=6.6, va="center", color="#333333")

    # (c) 组合失败
    ax_c = fig.add_axes([0.615, 0.16, 0.24, 0.70])
    panel(ax_c, load(os.path.join(FR, "fig1_c_fail.png")), "(c) composed task\nscene fails")
    badge(ax_c, "\u2717", RED)

    # (d) 场景级契约(validator 报告面板)
    ax_d = fig.add_axes([0.915, 0.16, 0.075, 0.70])
    ax_d.axis("off")
    card = mpatches.FancyBboxPatch((0.05, 0.02), 0.90, 0.96, transform=ax_d.transAxes,
                                   boxstyle="round,pad=0.03", fc="#eaf3fb", ec=BLUE, lw=1.4)
    ax_d.add_patch(card)
    ax_d.text(0.5, 0.90, "scene\ncontract", transform=ax_d.transAxes, ha="center",
              fontsize=7.6, color=BLUE, fontweight="bold")
    for j, t in enumerate(["closed ref.", "provenance", "task pre.", "interface"]):
        ax_d.text(0.12, 0.66 - j * 0.15, "\u2713 " + t, transform=ax_d.transAxes,
                  fontsize=6.2, color=GREEN, va="center")

    # 连接箭头
    arrow(fig, 0.258, 0.312, 0.51)
    arrow(fig, 0.558, 0.612, 0.51)
    arrow(fig, 0.858, 0.912, 0.51)

    fig.savefig(OUT_PDF, dpi=300, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    print("wrote", OUT_PDF, "and", OUT_PNG)


if __name__ == "__main__":
    main()
