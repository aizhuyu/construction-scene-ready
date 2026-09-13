#!/usr/bin/env python3
"""Run paired task-activated/all-loaded Isaac stage smoke tests."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import subprocess
import time
from pathlib import Path


SCENES = (
    "connection_plate_positioning",
    "pin_insertion",
    "sequential_assembly",
)
MODES = {
    "task_activated": "building_root.usda",
    "all_loaded": "building_root_all_loaded.usda",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--isaac-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--steps", type=int, default=240)
    parser.add_argument("--order-seed", type=int, default=20260727)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    project = args.project_root.expanduser().resolve()
    isaac_python = args.isaac_root.expanduser().resolve() / "python.sh"
    smoke_script = project / "scripts" / "isaac_stage_smoke.py"
    output = args.output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    conditions = [
        (scene, mode)
        for scene in SCENES
        for mode in sorted(MODES)
    ]
    randomizer = random.Random(args.order_seed)
    rows: list[dict[str, object]] = []

    for repeat in range(args.repeats):
        run_order = conditions.copy()
        randomizer.shuffle(run_order)
        for order_index, (scene, mode) in enumerate(run_order):
            run_id = f"RTX-STAGE-{repeat:02d}-{order_index:02d}-{scene}-{mode}"
            stage = (
                project
                / "generated"
                / "local-pipeline"
                / "usd"
                / scene
                / MODES[mode]
            )
            report_path = output / f"{run_id}.json"
            log_path = output / f"{run_id}.log"
            command = [
                str(isaac_python),
                str(smoke_script),
                "--stage",
                str(stage),
                "--output",
                str(report_path),
                "--steps",
                str(args.steps),
            ]
            wall_started = time.perf_counter()
            with log_path.open("w", encoding="utf-8") as log:
                completed = subprocess.run(
                    command,
                    cwd=project,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=args.timeout_seconds,
                    check=False,
                )
            wall_seconds = time.perf_counter() - wall_started
            report = (
                json.loads(report_path.read_text(encoding="utf-8"))
                if report_path.is_file()
                else {}
            )
            rows.append(
                {
                    "run_id": run_id,
                    "repeat": repeat,
                    "order_index": order_index,
                    "scene_id": scene,
                    "composition_mode": mode,
                    "stage_sha256": sha256(stage),
                    "status": report.get("status", "missing_report"),
                    "wrapper_returncode": completed.returncode,
                    "prim_count": report.get("prim_count"),
                    "rigid_body_count": report.get("rigid_body_count"),
                    "collision_api_count": report.get(
                        "collision_api_count"
                    ),
                    "load_seconds": report.get("load_seconds"),
                    "step_seconds": report.get("step_seconds"),
                    "total_seconds": report.get("total_seconds"),
                    "wall_seconds": wall_seconds,
                    "steps_completed": report.get("steps_completed"),
                    "report_path": report_path.name,
                    "log_path": log_path.name,
                }
            )

    csv_path = output / "stage-batch.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "protocol": "paired_task_activation_stage_smoke_v1",
        "order_seed": args.order_seed,
        "repeats": args.repeats,
        "steps": args.steps,
        "run_count": len(rows),
        "passed": sum(row["status"] == "passed" for row in rows),
        "failed": sum(row["status"] != "passed" for row in rows),
        "csv": csv_path.name,
    }
    summary_path = output / "stage-batch-summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
