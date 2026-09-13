#!/usr/bin/env python3
"""H4 分析: 场景就绪度分数 vs 机器人任务进度 的相关性.

读取 h4_evaluate.py 的输出, 计算相关性, 生成图表.

用法:
    python3 scripts/h4_analyze.py \
        --input generated/h4/results.json \
        --output-dir generated/h4/
"""
from __future__ import annotations
import argparse
import json
import os
from collections import defaultdict

import numpy as np


# =====================================================================
# 场景就绪度评分 (基于 CSR 验证规则的简化版)
# 每个物理变体对应的"场景就绪度"——越接近1越就绪
# =====================================================================

def readiness_score(fault: str, severity: float) -> float:
    """根据故障类型和严重度计算场景就绪度分数 (0=最差, 1=最好).

    这是对你 30 条 CSR 验证规则验证结果的连续近似。
    真实分数应由你的验证器对每个变体场景计算得出；
    这里用 severity 反推作为代理。
    """
    if fault == "none":
        return 1.0
    # 严重度越高, 就绪度越低
    # 不同故障类型的"致命程度"权重
    severity_weights = {
        "wrong_up_axis": 1.0,          # 坐标系错 = 最致命
        "wrong_units": 0.9,            # 单位错 = 非常致命
        "nonpositive_mass": 0.85,      # 质量错 = 物理崩溃
        "nonpositive_tolerance": 0.7,  # 公差错 = 装配失败
        "nonunit_interface_axis": 0.6, # 轴错 = 对不准
        "compound_interface_physics": 0.8,  # 复合
        "compound_mass_and_provenance": 0.75,
        "compound_frame_and_payload": 0.95,
    }
    weight = severity_weights.get(fault, 0.5)
    # 就绪度 = 1 - 严重度 × 致命权重
    return max(0.0, 1.0 - severity * weight)


def analyze(data: dict, output_dir: str):
    results = data["results"]

    # === 汇总: 每个变体的平均 reward ===
    variant_data = defaultdict(list)
    for r in results:
        if "error" in r:
            continue
        vid = r["variant_id"]
        variant_data[vid].append(r)

    # 构建分析表
    rows = []
    for vid, reps in variant_data.items():
        rep0 = reps[0]
        fault = rep0["fault"]
        severity = rep0["severity"]

        rewards = [r.get("mean_total_reward", 0) for r in reps]
        bolt_aligns = [r.get("mean_bolt_alignment", 0) for r in reps]
        approaches = [r.get("mean_approach_structure", 0) for r in reps]
        bolt_dists = [r.get("mean_bolt_target_distance", 0) for r in reps]

        row = {
            "variant_id": vid,
            "fault": fault,
            "severity": severity,
            "readiness_score": readiness_score(fault, severity),
            "n_repeats": len(reps),
            "reward_mean": np.mean(rewards),
            "reward_std": np.std(rewards),
            "bolt_alignment_mean": np.mean(bolt_aligns),
            "bolt_alignment_std": np.std(bolt_aligns),
            "approach_mean": np.mean(approaches),
            "approach_std": np.std(approaches),
            "bolt_dist_mean": np.mean(bolt_dists),
            "bolt_dist_std": np.std(bolt_dists),
        }
        rows.append(row)

    # 按 readiness 排序
    rows.sort(key=lambda r: r["readiness_score"], reverse=True)

    # === 相关性分析 ===
    readiness = np.array([r["readiness_score"] for r in rows])
    task_metrics = {
        "total_reward": np.array([r["reward_mean"] for r in rows]),
        "bolt_alignment": np.array([r["bolt_alignment_mean"] for r in rows]),
        "approach_structure": np.array([r["approach_mean"] for r in rows]),
        "bolt_target_distance": np.array([r["bolt_dist_mean"] for r in rows]),
    }

    print(f"\n{'='*70}")
    print(f"  H4 相关性分析: 场景就绪度 vs 任务进度")
    print(f"{'='*70}\n")

    correlations = {}
    for metric_name, metric_vals in task_metrics.items():
        if len(metric_vals) == 0 or np.all(metric_vals == metric_vals[0]):
            corr = 0.0
        else:
            corr = float(np.corrcoef(readiness, metric_vals)[0, 1])

        # bolt_target_distance 是负向指标(距离越大越差)
        direction = "正向" if metric_name != "bolt_target_distance" else "负向"
        expected_sign = "+" if direction == "正向" else "-"

        correlations[metric_name] = {
            "pearson_r": corr,
            "direction": direction,
            "supports_h4": (corr > 0.3) if direction == "正向" else (corr < -0.3),
        }

        print(f"  {metric_name:25s}: r = {corr:+.4f}  ({direction})  "
              f"{'✓ 支持H4' if correlations[metric_name]['supports_h4'] else '✗ 弱/不支持'}")

    print()

    # === 输出表格 ===
    print(f"{'variant_id':30s} {'readiness':>10s} {'reward':>10s} {'bolt_align':>10s} "
          f"{'approach':>10s} {'bolt_dist':>10s}")
    print("-" * 85)
    for r in rows:
        print(f"{r['variant_id']:30s} {r['readiness_score']:10.3f} "
              f"{r['reward_mean']:10.4f} {r['bolt_alignment_mean']:10.4f} "
              f"{r['approach_mean']:10.4f} {r['bolt_dist_mean']:10.4f}")

    # === 保存分析结果 JSON ===
    analysis = {
        "config": data.get("config", {}),
        "correlations": correlations,
        "h4_verdict": {
            "overall_support": sum(1 for c in correlations.values() if c["supports_h4"]),
            "total_metrics": len(correlations),
            "strongest_correlation": max(correlations.items(),
                                         key=lambda x: abs(x[1]["pearson_r"])),
        },
        "variant_summary": rows,
    }

    analysis_path = os.path.join(output_dir, "h4_analysis.json")
    with open(analysis_path, "w") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False, default=float)
    print(f"\n分析结果已保存: {analysis_path}")

    # === 生成图表 ===
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle("H4: Scene Readiness vs Task Progress", fontsize=14, fontweight="bold")

        metric_configs = [
            ("total_reward", "Total Reward", axes[0, 0], True),
            ("bolt_alignment", "Bolt Alignment Reward", axes[0, 1], True),
            ("approach_structure", "Approach Structure Reward", axes[1, 0], True),
            ("bolt_target_distance", "Bolt-Target Distance (m)", axes[1, 1], False),
        ]

        for metric_key, label, ax, positive in metric_configs:
            vals = task_metrics[metric_key]
            ax.scatter(readiness, vals, s=80, alpha=0.7, edgecolors="black", linewidth=0.5)

            # 趋势线
            if not np.all(vals == vals[0]):
                z = np.polyfit(readiness, vals, 1)
                p = np.poly1d(z)
                x_fit = np.linspace(readiness.min(), readiness.max(), 50)
                ax.plot(x_fit, p(x_fit), "r--", alpha=0.5)

            r_val = correlations[metric_key]["pearson_r"]
            ax.set_xlabel("Scene Readiness Score")
            ax.set_ylabel(label)
            ax.set_title(f"{label}  (r = {r_val:+.3f})")
            ax.grid(True, alpha=0.3)
            if not positive:
                ax.set_ylabel(label + " (lower = better)")

        plt.tight_layout()
        fig_path = os.path.join(output_dir, "h4_correlation.png")
        plt.savefig(fig_path, dpi=150, bbox_inches="tight")
        print(f"图表已保存: {fig_path}")
        plt.close()
    except ImportError:
        print("(matplotlib 不可用, 跳过图表生成)")

    # === 最终判断 ===
    print(f"\n{'='*70}")
    verdict = analysis["h4_verdict"]
    print(f"  H4 判定:")
    print(f"    支持指标数: {verdict['overall_support']}/{verdict['total_metrics']}")
    strongest = verdict["strongest_correlation"]
    print(f"    最强相关: {strongest[0]} (r={strongest[1]['pearson_r']:+.4f})")
    if verdict["overall_support"] >= 2:
        print(f"    → 结论: H4 成立 (场景就绪度能预测任务进度)")
    elif verdict["overall_support"] >= 1:
        print(f"    → 结论: H4 部分成立 (需更多数据验证)")
    else:
        print(f"    → 结论: H4 暂不支持 (检查策略质量或实验设计)")
    print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True, help="h4_evaluate 输出的 JSON")
    parser.add_argument("--output-dir", type=str, required=True)
    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    os.makedirs(args.output_dir, exist_ok=True)
    analyze(data, args.output_dir)


if __name__ == "__main__":
    main()
