# -*- coding: utf-8 -*-
"""高清任务序列面板采集: v2 环境 2560x1440, 一个成功回合的四个关键时刻.

面板: overview(全景) / approach(持栓接近) / align(对准孔口) / inserting(进给)
"""
import argparse

from omni.isaac.lab.app import AppLauncher

import cli_args  # isort: skip

parser = argparse.ArgumentParser()
parser.add_argument("--task", type=str, default="Isaac-Assembly-G1-Play-v2")
parser.add_argument("--ckpt_path", type=str, required=True)
parser.add_argument("--out_dir", type=str, required=True)
parser.add_argument("--seed", type=int, default=42)
cli_args.add_rsl_rl_args(parser)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
args_cli.headless = True
args_cli.enable_cameras = True

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import os

import gymnasium as gym
import numpy as np
import torch

from rsl_rl.runners import OnPolicyRunner

import omni.isaac.lab_tasks  # noqa: F401
from omni.isaac.lab_tasks.utils import parse_env_cfg
from omni.isaac.lab_tasks.utils.wrappers.rsl_rl import RslRlVecEnvWrapper

INSERT_AXIS = 1
TARGET = 0.02
ALIGN = 0.012
OFFSET = 0.045

# 每步保存条件(命中即抓该帧)
STAGES = [
    ("overview", lambda s, d, p: s == 30),                       # 全景: 回合早期
    ("approach", lambda s, d, p: p < 0.05 and d < 0.01),        # 持栓接近: 距孔 5cm 内
    ("align", lambda s, d, p: p < ALIGN and d < 0.006),          # 对准: 对准阈值内 深度<6mm
    ("inserting", lambda s, d, p: p < ALIGN and 0.006 <= d < TARGET),  # 进给: 深度 6-20mm
]
CAMS = {
    "overview": ((-2.0, 0.8, 2.0), (0.0, 0.3, 0.85)),
    "approach": ((0.42, 0.22, 0.95), (0.05, 0.12, 0.90)),
    "align": ((-0.30, 0.13, 0.90), (0.05, 0.11, 0.90)),
    "inserting": ((-0.30, 0.13, 0.90), (0.05, 0.11, 0.90)),
}


def main():
    env_cfg = parse_env_cfg(args_cli.task, device=args_cli.device, num_envs=1)
    env_cfg.seed = args_cli.seed
    env_cfg.viewer.resolution = (2560, 1440)
    agent_cfg = cli_args.parse_rsl_rl_cfg(args_cli.task, args_cli)
    agent_cfg.seed = args_cli.seed

    env = gym.make(args_cli.task, cfg=env_cfg, render_mode="rgb_array")
    env = RslRlVecEnvWrapper(env)
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    runner.load(args_cli.ckpt_path)
    policy = runner.get_inference_policy(device=env.unwrapped.device)

    unwrapped = env.unwrapped
    bolt = unwrapped.scene["assembly_bolt"]
    hole = unwrapped.scene["bolt_hole"]
    out_dir = os.path.expanduser(args_cli.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    captured = {}
    obs, _ = env.get_observations()
    step = 0
    for episode in range(8):
        done_this_ep = False
        while True:
            with torch.inference_mode():
                actions = policy(obs)
            obs, rew, dones, extras = env.step(actions)
            step += 1
            bolt_pos = bolt.data.root_pos_w[0, :3]
            hole_pos = hole.data.root_pos_w[0, :3]
            depth = float(torch.clamp(hole_pos[INSERT_AXIS] + OFFSET - bolt_pos[INSERT_AXIS], min=0.0))
            perp = float(torch.norm(bolt_pos[[0, 2]] - hole_pos[[0, 2]]))
            for name, cond in STAGES:
                if name not in captured and cond(step, depth, perp):
                    eye, lookat = CAMS[name]
                    unwrapped.viewport_camera_controller.update_view_location(eye=eye, lookat=lookat)
                    for _ in range(3):  # 走3步让机位生效
                        obs, rew2, dones2, extras2 = env.step(actions)
                    frame = unwrapped.render()
                    if frame is not None:
                        captured[name] = np.asarray(frame)
                        print(f"[INFO] captured {name} at step {step} (perp={perp*1000:.1f}mm depth={depth*1000:.1f}mm)", flush=True)
            if len(captured) == len(STAGES):
                break
            if bool(dones[0]):
                done_this_ep = True
                break
        if len(captured) == len(STAGES) or done_this_ep:
            if len(captured) == len(STAGES):
                break
            print(f"[INFO] episode {episode} ended with {len(captured)} frames, retrying", flush=True)
            captured = {}
            step = 0

    from PIL import Image
    for name, frame in captured.items():
        path = os.path.join(out_dir, f"panel_{name}.png")
        Image.fromarray(frame[..., :3] if frame.shape[-1] == 4 else frame).save(path)
        print(f"RESULT saved {path}", flush=True)
    print(f"RESULT captured {len(captured)}/4", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
