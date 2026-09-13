#!/usr/bin/env python3
"""Load and step one compiled ConstructionSceneReady stage in Isaac Sim.

This script is intentionally small and version-tolerant.  It is executed with
Isaac Sim's ``python.sh`` rather than the project's Mac virtual environment.
The emitted JSON is a raw run artefact; it is not interpreted as task success.
"""

from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path

# Isaac Sim 4.2 emits a deprecation notice for this import path, but on the
# frozen 4.2 workstation it is the stable launcher.  The newer ``isaacsim``
# import path is reserved for the separately tested 4.5+ environment.
from omni.isaac.kit import SimulationApp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=60)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stage_path = args.stage.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    if not stage_path.is_file():
        raise FileNotFoundError(stage_path)

    application = SimulationApp(
        {
            "headless": True,
            "renderer": "RayTracedLighting",
            "width": 640,
            "height": 480,
        }
    )
    started = time.perf_counter()
    report: dict[str, object] = {
        "stage": str(stage_path),
        "steps_requested": args.steps,
        "python": platform.python_version(),
        "status": "started",
    }

    try:
        import omni.usd
        from omni.isaac.core import World
        from omni.isaac.core.utils.stage import open_stage
        from pxr import UsdPhysics

        opened = bool(open_stage(str(stage_path)))
        application.update()
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("Isaac Sim did not expose a USD stage")

        load_finished = time.perf_counter()
        prims = [prim for prim in stage.Traverse()]
        rigid_bodies = [
            prim.GetPath().pathString
            for prim in prims
            if prim.HasAPI(UsdPhysics.RigidBodyAPI)
        ]
        colliders = [
            prim.GetPath().pathString
            for prim in prims
            if prim.HasAPI(UsdPhysics.CollisionAPI)
        ]

        world = World()
        world.reset()
        for _ in range(args.steps):
            world.step(render=False)
        stepped = time.perf_counter()

        report.update(
            {
                "status": "passed",
                "open_stage_returned": opened,
                "prim_count": len(prims),
                "rigid_body_count": len(rigid_bodies),
                "collision_api_count": len(colliders),
                "rigid_body_paths": rigid_bodies,
                "collider_paths": colliders,
                "load_seconds": load_finished - started,
                "step_seconds": stepped - load_finished,
                "total_seconds": stepped - started,
                "steps_completed": args.steps,
            }
        )
    except Exception as exc:
        report.update(
            {
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "total_seconds": time.perf_counter() - started,
            }
        )
    finally:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        application.close()

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
