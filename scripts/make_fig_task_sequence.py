#!/usr/bin/env python3
"""Compose annotated 2x2 task-sequence figure from high-res Isaac Lab panels.

Panels (2560x1440 PNG): overview / approach / align / inserting.
Output: fig_task_sequence.pdf + fig_task_sequence.png (300 dpi, full text width).
Annotation anchors are in axes fraction (x, y), origin bottom-left.
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
    "align": "(c) Shank aligned with hole",
    "inserting": "(d) Insertion (depth gate 20 mm)",
}

# annotations: panel -> list of (text, target_xy, text_xy)
ANNOT = {
    "overview": [
        ("portal-frame\ncolumn", (0.06, 0.56), (0.02, 0.88)),
        ("1.3 m beam,\nsupported both ends", (0.32, 0.56), (0.14, 0.76)),
        ("end plate,\n2x2 hole group", (0.57, 0.64), (0.68, 0.86)),
        ("Unitree G1", (0.44, 0.33), (0.08, 0.14)),
    ],
    "approach": [
        ("M20 bolt (in-hand)", (0.85, 0.41), (0.60, 0.14)),
        ("G1 dexterous hand", (0.70, 0.31), (0.30, 0.08)),
        ("end plate", (0.48, 0.56), (0.18, 0.84)),
        ("beam lower flange", (0.70, 0.63), (0.52, 0.86)),
    ],
    "align": [
        ("bolt shank", (0.40, 0.48), (0.10, 0.68)),
        ("target hole", (0.50, 0.47), (0.64, 0.70)),
        ("lateral error < 12 mm", (0.46, 0.46), (0.52, 0.14)),
    ],
    "inserting": [
        ("shank entering hole", (0.44, 0.47), (0.10, 0.66)),
        ("end plate", (0.52, 0.38), (0.68, 0.18)),
        ("insertion depth\n6-20 mm", (0.48, 0.50), (0.60, 0.84)),
    ],
}

ARROW = dict(arrowstyle="-|>", color="white", lw=1.6,
             shrinkA=2, shrinkB=2, mutation_scale=14)
BBOX = dict(boxstyle="round,pad=0.25", fc="black", ec="white", alpha=0.65)


def main():
    fig, axes = plt.subplots(2, 2, figsize=(7.08, 4.35))
    for ax, name in zip(axes.flat, PANELS):
        img = Image.open(os.path.join(PANEL_DIR, f"panel_{name}.png"))
        ax.imshow(img)
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_title(TITLES[name], fontsize=8.5, loc="left", pad=2)
        for text, xy, xytext in ANNOT.get(name, []):
            ax.annotate(text, xy=xy, xytext=xytext,
                        xycoords="axes fraction", textcoords="axes fraction",
                        fontsize=6.8, color="white", ha="left", va="center",
                        arrowprops=ARROW, bbox=BBOX, zorder=5)
    fig.tight_layout(pad=0.4, h_pad=0.6, w_pad=0.6)
    fig.savefig(OUT_PDF, dpi=300)
    fig.savefig(OUT_PNG, dpi=300)
    print("wrote", OUT_PDF, "and", OUT_PNG)


if __name__ == "__main__":
    main()
