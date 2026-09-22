#!/usr/bin/env python3
"""Compose numbered-marker 2x2 task-sequence figure (journal-clean style).

Panels (2560x1440 PNG): overview / approach / align / inserting.
Output: fig_task_sequence.pdf + fig_task_sequence.png (300 dpi, full width).
Numbered circle markers on features; one shared legend at the bottom.
Marker anchors are in axes fraction (x, y), origin bottom-left.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

PANEL_DIR = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/fig_panels")
OUT_PDF = sys.argv[2] if len(sys.argv) > 2 else "fig_task_sequence.pdf"
OUT_PNG = os.path.splitext(OUT_PDF)[0] + ".png"

PANELS = ["overview", "approach", "align", "inserting"]
TITLES = {
    "overview": "(a) Task overview",
    "approach": "(b) Grasped bolt approaches plate",
    "align": "(c) Shank aligned (lateral error < 12 mm)",
    "inserting": "(d) Insertion (depth 6-20 mm)",
}

# panel -> list of (number, x, y)
MARKERS = {
    "overview": [(1, 0.055, 0.60), (2, 0.32, 0.60), (3, 0.575, 0.64), (4, 0.44, 0.33)],
    "approach": [(2, 0.70, 0.635), (3, 0.485, 0.56), (5, 0.855, 0.42), (6, 0.70, 0.30)],
    "align": [(7, 0.40, 0.49), (8, 0.505, 0.47)],
    "inserting": [(7, 0.44, 0.47), (3, 0.525, 0.38)],
}

LEGEND = {
    1: "portal-frame column",
    2: "1.3 m beam, both-ends supported",
    3: "end plate, 2x2 hole group",
    4: "Unitree G1",
    5: "M20 bolt (in-hand)",
    6: "G1 dexterous hand",
    7: "bolt shank",
    8: "target hole",
}


def draw_marker(ax, num, x, y):
    ax.add_patch(plt.Circle((x, y), 0.028, transform=ax.transAxes,
                            facecolor="black", edgecolor="white", lw=1.2, zorder=6))
    ax.text(x, y, str(num), transform=ax.transAxes, color="white",
            fontsize=7.5, fontweight="bold", ha="center", va="center", zorder=7)


def main():
    fig, axes = plt.subplots(2, 2, figsize=(7.08, 4.55))
    for ax, name in zip(axes.flat, PANELS):
        img = Image.open(os.path.join(PANEL_DIR, f"panel_{name}.png"))
        ax.imshow(img)
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_title(TITLES[name], fontsize=8.2, loc="left", pad=2)
        for num, x, y in MARKERS.get(name, []):
            draw_marker(ax, num, x, y)

    # 底部共享图例(两行)
    items = [f"{k} {v}" for k, v in LEGEND.items()]
    line1 = "    ".join(items[:4])
    line2 = "    ".join(items[4:])
    fig.text(0.5, 0.045, line1, ha="center", va="center", fontsize=7.0)
    fig.text(0.5, 0.012, line2, ha="center", va="center", fontsize=7.0)

    fig.tight_layout(pad=0.4, h_pad=0.7, w_pad=0.5, rect=(0, 0.07, 1, 1))
    fig.savefig(OUT_PDF, dpi=300)
    fig.savefig(OUT_PNG, dpi=300)
    print("wrote", OUT_PDF, "and", OUT_PNG)


if __name__ == "__main__":
    main()
