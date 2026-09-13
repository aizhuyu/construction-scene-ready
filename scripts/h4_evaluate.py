#!/usr/bin/env python3
"""H4 评估调度器 v2: 更科学的扰动矩阵.

设计原则:
- 去掉坐标系翻转(灾难性,不体现渐进退化)
- 聚焦装配参数的渐进扰动(尺寸/质量/摩擦/位置/公差)
- 每种故障5个强度,体现"越好越成功"的梯度
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time

PERTURBATIONS = [
    # === 基线 ===
    {"id": "baseline", "fault": "none", "severity": 0.0, "changes": {}},

    # === 螺栓尺寸偏差 (wrong_units的渐进版) ===
    {"id": "bolt_size_95pct", "fault": "dimension", "severity": 0.05, "changes": {"scale_all": 0.95}},
    {"id": "bolt_size_80pct", "fault": "dimension", "severity": 0.20, "changes": {"scale_all": 0.80}},
    {"id": "bolt_size_50pct", "fault": "dimension", "severity": 0.50, "changes": {"scale_all": 0.50}},
    {"id": "bolt_size_20pct", "fault": "dimension", "severity": 0.80, "changes": {"scale_all": 0.20}},

    # === 螺栓质量异常 (nonpositive_mass的渐进版) ===
    {"id": "bolt_mass_50pct", "fault": "mass", "severity": 0.25, "changes": {"bolt_mass_scale": 0.5}},
    {"id": "bolt_mass_10pct", "fault": "mass", "severity": 0.50, "changes": {"bolt_mass_scale": 0.1}},
    {"id": "bolt_mass_1pct", "fault": "mass", "severity": 0.75, "changes": {"bolt_mass_scale": 0.01}},
    {"id": "bolt_mass_zero", "fault": "mass", "severity": 0.90, "changes": {"bolt_mass_scale": 0.0}},

    # === 螺栓过盈 (nonpositive_tolerance的渐进版) ===
    {"id": "bolt_oversize_1mm", "fault": "tolerance", "severity": 0.20, "changes": {"bolt_radius_delta": 0.001}},
    {"id": "bolt_oversize_3mm", "fault": "tolerance", "severity": 0.40, "changes": {"bolt_radius_delta": 0.003}},
    {"id": "bolt_oversize_5mm", "fault": "tolerance", "severity": 0.60, "changes": {"bolt_radius_delta": 0.005}},
    {"id": "bolt_oversize_10mm", "fault": "tolerance", "severity": 0.80, "changes": {"bolt_radius_delta": 0.010}},

    # === 螺栓摩擦力变化 (影响抓取稳定性) ===
    {"id": "bolt_fric_low", "fault": "friction", "severity": 0.30, "changes": {"bolt_friction": 0.1}},
    {"id": "bolt_fric_verylow", "fault": "friction", "severity": 0.60, "changes": {"bolt_friction": 0.01}},
    {"id": "bolt_fric_zero", "fault": "friction", "severity": 0.90, "changes": {"bolt_friction": 0.0}},

    # === 螺栓初始位置偏移 (装配定位误差) ===
    {"id": "bolt_pos_off_10cm", "fault": "position", "severity": 0.20, "changes": {"bolt_pos_offset": [0.1, 0.0, 0.0]}},
    {"id": "bolt_pos_off_30cm", "fault": "position", "severity": 0.40, "changes": {"bolt_pos_offset": [0.3, 0.0, 0.0]}},
    {"id": "bolt_pos_off_50cm", "fault": "position", "severity": 0.60, "changes": {"bolt_pos_offset": [0.5, 0.0, 0.0]}},
    {"id": "bolt_pos_off_1m", "fault": "position", "severity": 0.80, "changes": {"bolt_pos_offset": [1.0, 0.0, 0.0]}},

    # === 螺栓初始旋转 (nonunit_interface_axis的渐进版) ===
    {"id": "bolt_rot_15deg", "fault": "rotation", "severity": 0.20, "changes": {"bolt_rot_z": 0.262}},
    {"id": "bolt_rot_30deg", "fault": "rotation", "severity": 0.40, "changes": {"bolt_rot_z": 0.524}},
    {"id": "bolt_rot_60deg", "fault": "rotation", "severity": 0.60, "changes": {"bolt_rot_z": 1.047}},
    {"id": "bolt_rot_90deg", "fault": "rotation", "severity": 0.80, "changes": {"bolt_rot_z": 1.571}},

    # === 复合: 位置+公差 ===
    {"id": "compound_pos_tol_mild", "fault": "compound", "severity": 0.40,
     "changes": {"bolt_pos_offset": [0.2, 0.0, 0.0], "bolt_radius_delta": 0.002}},
    {"id": "compound_pos_tol_severe", "fault": "compound", "severity": 0.70,
     "changes": {"bolt_pos_offset": [0.5, 0.0, 0.0], "bolt_radius_delta": 0.006}},

    # === 复合: 质量+摩擦 ===
    {"id": "compound_mass_fric", "fault": "compound", "severity": 0.60,
     "changes": {"bolt_mass_scale": 0.05, "bolt_friction": 0.05}},

    # === 复合: 尺寸+旋转 ===
    {"id": "compound_size_rot", "fault": "compound", "severity": 0.60,
     "changes": {"scale_all": 0.6, "bolt_rot_z": 0.6}},

    # === 复合: 全部轻微 ===
    {"id": "compound_all_mild", "fault": "compound", "severity": 0.50,
     "changes": {"scale_all": 0.8, "bolt_mass_scale": 0.5, "bolt_friction": 0.3, "bolt_rot_z": 0.3}},

    # === 复合: 全部严重 ===
    {"id": "compound_all_severe", "fault": "compound", "severity": 0.85,
     "changes": {"scale_all": 0.4, "bolt_mass_scale": 0.1, "bolt_friction": 0.1, "bolt_rot_z": 0.8}},
]

ISAACLAB_DIR = os.path.expanduser("~/IsaacLab")
SINGLE_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "h4_single_variant.py")


def main():
    parser = argparse.ArgumentParser(description="H4 evaluation orchestrator v2")
    parser.add_argument("--checkpoint", type=str, required=True)
    parser.add_argument("--task", type=str, default="Isaac-SteelAssembly-G1-Play-v0")
    parser.add_argument("--num-envs", type=int, default=64)
    parser.add_argument("--steps", type=int, default=1500)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--device", type=str, default="cuda:0")
    args = parser.parse_args()

    output_path = os.path.expanduser(args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    existing_results = []
    done_keys = set()
    if os.path.exists(output_path):
        try:
            old = json.load(open(output_path))
            existing_results = old.get("results", [])
            done_keys = {(r["variant_id"], r.get("repeat", 0)) for r in existing_results}
        except Exception:
            pass

    total = len(PERTURBATIONS) * args.repeats
    print(f"\n{'#'*60}")
    print(f"#  H4 Evaluation v2 ({len(PERTURBATIONS)} variants × {args.repeats} = {total})")
    print(f"#  Steps/rollout: {args.steps} (~{args.steps*0.02:.0f}s sim)")
    print(f"#{'#'*60}\n")

    all_results = list(existing_results)
    start_time = time.time()
    current = len(all_results)

    for pert in PERTURBATIONS:
        for rep in range(args.repeats):
            key = (pert["id"], rep)
            if key in done_keys:
                continue

            current += 1
            vid = pert["id"]
            print(f"[{current}/{total}] {vid} r{rep} (sev={pert['severity']})")

            single_output = os.path.join(os.path.dirname(output_path),
                                         f"tmp_{vid}_{rep}.json")
            changes_file = os.path.join(os.path.dirname(output_path),
                                        f"tmp_changes_{vid}_{rep}.json")
            json.dump(pert["changes"], open(changes_file, "w"))

            cmd = [
                os.path.join(ISAACLAB_DIR, "isaaclab.sh"), "-p",
                SINGLE_SCRIPT,
                "--checkpoint", args.checkpoint,
                "--task", args.task,
                "--num-envs", str(args.num_envs),
                "--steps", str(args.steps),
                "--variant-id", vid,
                "--fault", pert["fault"],
                "--severity", str(pert["severity"]),
                "--changes-file", changes_file,
                "--output", single_output,
            ]

            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=600,
                    cwd=ISAACLAB_DIR,
                    env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                         "LC_ALL": "en_US.UTF-8", "LANG": "en_US.UTF-8"},
                )
                if result.returncode != 0:
                    err_lines = [l for l in result.stderr.split("\n")
                                 if any(x in l for x in ["Error", "error", "Traceback"])]
                    err = err_lines[-1][:200] if err_lines else f"exit {result.returncode}"
                    print(f"  ✗ {err}")
                    result_data = {"variant_id": vid, "fault": pert["fault"],
                                   "severity": pert["severity"], "repeat": rep, "error": err}
                elif os.path.exists(single_output):
                    result_data = json.load(open(single_output))
                    result_data["repeat"] = rep
                    rew = result_data.get("mean_total_reward", 0)
                    dist = result_data.get("mean_bolt_target_distance", 0)
                    print(f"  ✓ reward={rew:.3f} bolt_dist={dist:.3f}")
                    os.remove(single_output)
                else:
                    result_data = {"variant_id": vid, "fault": pert["fault"],
                                   "severity": pert["severity"], "repeat": rep,
                                   "error": "no output"}
            except Exception as e:
                print(f"  ✗ {e}")
                result_data = {"variant_id": vid, "fault": pert["fault"],
                               "severity": pert["severity"], "repeat": rep, "error": str(e)}

            try:
                os.remove(changes_file)
            except Exception:
                pass

            all_results.append(result_data)
            with open(output_path, "w") as f:
                json.dump({"checkpoint": args.checkpoint,
                           "config": {"num_envs": args.num_envs, "steps": args.steps,
                                      "repeats": args.repeats},
                           "total_variants": len(PERTURBATIONS),
                           "results": all_results}, f, indent=2, ensure_ascii=False)

    elapsed = time.time() - start_time
    success = sum(1 for r in all_results if "error" not in r)
    print(f"\n{'='*60}")
    print(f"  完成! {success}/{len(all_results)} 成功, {elapsed/60:.1f} 分钟")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
