#!/usr/bin/env python3
"""H4 单变体执行(极简版): 只记录total_reward+bolt_dist,不提取分项reward."""
from __future__ import annotations
import argparse, copy, json, math, os, torch
from omni.isaac.lab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--checkpoint", type=str, required=True)
parser.add_argument("--task", type=str, default="Isaac-SteelAssembly-G1-Play-v0")
parser.add_argument("--num-envs", type=int, default=64)
parser.add_argument("--steps", type=int, default=1500)
parser.add_argument("--variant-id", type=str, required=True)
parser.add_argument("--fault", type=str, required=True)
parser.add_argument("--severity", type=float, required=True)
parser.add_argument("--changes-file", type=str, default="")
parser.add_argument("--output", type=str, required=True)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
args_cli.headless = True
args_cli.enable_cameras = True
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym
from rsl_rl.runners import OnPolicyRunner
import omni.isaac.lab_tasks
from omni.isaac.lab_tasks.utils import parse_env_cfg
from omni.isaac.lab_tasks.utils.parse_cfg import load_cfg_from_registry
from omni.isaac.lab_tasks.utils.wrappers.rsl_rl import RslRlOnPolicyRunnerCfg, RslRlVecEnvWrapper

def apply_perturbation(env_cfg, changes):
    cfg = copy.deepcopy(env_cfg)
    if "gravity" in changes:
        cfg.sim.gravity = tuple(changes["gravity"])
    if "bolt_mass_scale" in changes:
        scale = changes["bolt_mass_scale"]
        bolt = cfg.scene.steel_bolt
        if hasattr(bolt.spawn, "mass_props") and bolt.spawn.mass_props:
            bolt.spawn = bolt.spawn.replace(mass_props=bolt.spawn.mass_props.replace(density=7850.0 * scale if scale > 0 else 0.001))
    if "bolt_radius_delta" in changes:
        bolt = cfg.scene.steel_bolt
        bolt.spawn = bolt.spawn.replace(radius=0.012 + changes["bolt_radius_delta"])
    if "bolt_rot_z" in changes:
        rot = changes["bolt_rot_z"]
        cfg.scene.steel_bolt.init_state = cfg.scene.steel_bolt.init_state.replace(rot=(math.cos(rot/2), 0.0, 0.0, math.sin(rot/2)))
    if "bolt_friction" in changes:
        fric = changes["bolt_friction"]
        bolt = cfg.scene.steel_bolt
        if hasattr(bolt.spawn, "physics_material") and bolt.spawn.physics_material:
            bolt.spawn = bolt.spawn.replace(physics_material=bolt.spawn.physics_material.replace(static_friction=fric, dynamic_friction=fric))
    if "scale_all" in changes:
        scale = changes["scale_all"]
        bolt = cfg.scene.steel_bolt
        if hasattr(bolt.spawn, "radius"):
            bolt.spawn = bolt.spawn.replace(radius=0.012*scale, height=0.05*scale)
    if "bolt_pos_offset" in changes:
        offset = changes["bolt_pos_offset"]
        orig = (1.0, 0.3, 0.05)
        cfg.scene.steel_bolt.init_state = cfg.scene.steel_bolt.init_state.replace(pos=tuple(o+d for o,d in zip(orig, offset)))
    return cfg

def main():
    device = args_cli.device
    changes = json.load(open(args_cli.changes_file)) if args_cli.changes_file else {}
    base_env_cfg = parse_env_cfg(args_cli.task, device=device, num_envs=args_cli.num_envs, use_fabric=True)
    env_cfg = apply_perturbation(base_env_cfg, changes)
    env_cfg.scene.num_envs = args_cli.num_envs
    env = gym.make(args_cli.task, cfg=env_cfg)
    env = RslRlVecEnvWrapper(env)
    agent_cfg = load_cfg_from_registry(args_cli.task, "rsl_rl_cfg_entry_point")
    agent_cfg = agent_cfg.replace(device=device, experiment_name="h4_eval")
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=device)
    runner.load(args_cli.checkpoint)
    policy = runner.get_inference_policy(device=device)

    obs, _ = env.get_observations()
    n = args_cli.num_envs
    total_reward = torch.zeros(n, device=device)

    with torch.inference_mode():
        for step in range(args_cli.steps):
            actions = policy(obs)
            obs, reward, dones, extras = env.step(actions)
            total_reward += reward

    # bolt最终位置
    bolt_dist = -1.0
    try:
        bolt_obj = env.unwrapped.scene["steel_bolt"]
        final_pos = bolt_obj.data.root_pos_w.detach()
        target = torch.tensor([2.055, 0.10, 1.5], device=device).unsqueeze(0)
        bolt_dist = torch.norm(final_pos[:, :3] - target, dim=-1).mean().item()
    except Exception:
        pass

    # G1位置
    g1_pos = [0, 0]
    g1_height = 0
    try:
        robot = env.unwrapped.scene["robot"]
        g1_pos = robot.data.root_pos_w.detach()[:, :2].mean(dim=0).tolist()
        g1_height = robot.data.root_pos_w.detach()[:, 2].mean().item()
    except Exception:
        pass

    result = {
        "variant_id": args_cli.variant_id,
        "fault": args_cli.fault,
        "severity": args_cli.severity,
        "changes": changes,
        "num_envs": n,
        "steps": args_cli.steps,
        "mean_total_reward": total_reward.mean().item(),
        "std_total_reward": total_reward.std().item(),
        "mean_bolt_target_distance": bolt_dist,
        "g1_final_pos_xy": g1_pos,
        "g1_final_height": g1_height,
    }
    print(f"  reward={result['mean_total_reward']:.3f} bolt_dist={result['mean_bolt_target_distance']:.3f} g1_h={g1_height:.2f}")
    with open(args_cli.output, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    env.close()
    simulation_app.close()

if __name__ == "__main__":
    main()
