#!/usr/bin/env python3
"""fig10: 实验场景实现(真实仿真渲染) + 手指关节动作轨迹.

输入:
  --frames-dir: render_scene_anatomy.py 的 4 张场景渲染
  --traj: record_finger_trajectory.py 的 JSON
输出: paper/figures/fig10_experimental_setup.{pdf,png}
"""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

JOINT_LABEL = {
    "right_zero_joint": "j0 (thumb rot.)",
    "right_one_joint": "j1",
    "right_two_joint": "j2",
    "right_three_joint": "j3",
    "right_four_joint": "j4",
    "right_five_joint": "j5",
    "right_six_joint": "j6",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames-dir", required=True)
    ap.add_argument("--traj", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    fig = plt.figure(figsize=(7.5, 4.6))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.15], hspace=0.32, wspace=0.06)

    # 上排: 两个真实渲染机位(全景 + 节点特写)
    for col, (name, title) in enumerate([("side", "(a) scene overview (real render)"),
                                          ("node", "(b) connection node close-up")]):
        ax = fig.add_subplot(gs[0, col])
        img = np.asarray(Image.open(Path(args.frames_dir) / f"scene_{name}.png"))
        ax.imshow(img)
        ax.set_title(title, fontsize=7.5, loc="left")
        ax.axis("off")

    # 下排跨两列: 手指关节轨迹 + 几何误差
    ax1 = fig.add_subplot(gs[1, :])
    data = json.loads(Path(args.traj).read_text())
    traj = [x for x in data["trajectory"] if x["step"] > 10]  # 去 reset 瞬态
    steps = np.array([t["step"] for t in traj])
    joints = np.array([t["joints"] for t in traj])
    perp = np.array([t["perp_mm"] for t in traj])
    depth = np.array([t["depth_mm"] for t in traj])

    cmap = plt.get_cmap("tab10")
    for j in range(joints.shape[1]):
        ax1.plot(steps, joints[:, j], linewidth=1.0, color=cmap(j % 10),
                 label=JOINT_LABEL.get(data["finger_joints"][j], data["finger_joints"][j]))
    ax1.set_xlabel("control step (30 Hz)", fontsize=7)
    ax1.set_ylabel("right-hand finger joint pos (rad)", fontsize=7)
    ax1.tick_params(labelsize=6)
    ax1.legend(fontsize=5.5, ncol=7, loc="upper right", framealpha=0.9)
    ax1.set_title("(c) finger joint actions during a successful insertion episode", fontsize=7.5, loc="left")

    ax2 = ax1.twinx()
    ax2.plot(steps, perp, color="#D55E00", linewidth=1.6, linestyle="--", label="alignment error (mm)")
    ax2.plot(steps, depth, color="#0072B2", linewidth=1.6, linestyle="-.", label="insertion depth (mm)")
    ax2.axhline(12.0, color="#D55E00", linewidth=0.6, alpha=0.4)
    ax2.axhline(20.0, color="#0072B2", linewidth=0.6, alpha=0.4)
    ax2.set_ylim(0, 150)
    ax2.set_ylabel("task geometry (mm)", fontsize=7)
    ax2.tick_params(labelsize=6)
    ax2.legend(fontsize=5.5, loc="center right")

    for ext in ("pdf", "png"):
        fig.savefig(args.out + "." + ext, dpi=600, bbox_inches="tight")
    print(f"wrote {args.out}.pdf/.png")


if __name__ == "__main__":
    main()
