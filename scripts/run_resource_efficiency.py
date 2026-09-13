#!/usr/bin/env python3
"""A3 resource-efficiency measurement: task-activated vs all-loaded composition.

For every test-partition scene, compiles both USD roots and reports per
composition mode: active prim count, cold load time (median of 5 opens, each
on a freshly copied tree so the USD layer cache cannot serve a warm hit),
and peak RSS delta of the first open.  Collision-query cost is an RTX-side
metric and is left empty in this CPU run (see generated/rtx smoke reports).

Rows follow the registered schema of data/results/resource_efficiency.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
import resource
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from construction_scene_ready.suites import build_scenes  # noqa: E402
from construction_scene_ready.usd_compiler import compile_usd  # noqa: E402
from construction_scene_ready.usd_metrics import inspect_composition  # noqa: E402

RESULT_CSV = REPO / "data" / "results" / "resource_efficiency.csv"
CSV_FIELDS = (
    "case_id", "scenario", "layer_condition", "active_prims", "peak_cpu_mb",
    "peak_gpu_mb", "load_time_s", "collision_query_ms",
)
MODES = (
    ("task_activated", "building_root.usda"),
    ("all_loaded", "building_root_all_loaded.usda"),
)
REPEATS = 5

MEASURE_SNIPPET = """
import json, resource, shutil, sys, tempfile
from pathlib import Path
from time import perf_counter
from pxr import Usd

root = Path(sys.argv[1])
repeats = int(sys.argv[2])
times = []
first_peak = None
for i in range(repeats):
    with tempfile.TemporaryDirectory() as tmp:
        copied = Path(tmp) / "tree"
        shutil.copytree(root.parent, copied)
        target = copied / root.name
        before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        start = perf_counter()
        stage = Usd.Stage.Open(str(target), Usd.Stage.LoadAll)
        _ = list(stage.Traverse())
        times.append(perf_counter() - start)
        after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if first_peak is None:
            first_peak = (after - before) / 1024.0
        del stage
times.sort()
print(json.dumps({
    "load_time_s": times[len(times) // 2],
    "min_time_s": times[0],
    "max_time_s": times[-1],
    "peak_cpu_mb": first_peak,
}))
"""


def measure(root: Path, repeats: int) -> dict:
    out = subprocess.run(
        [sys.executable, "-c", MEASURE_SNIPPET, str(root), str(repeats)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="A3-CPU-RES-0001")
    args = parser.parse_args()

    rows = []
    report = {"run_id": args.run_id, "repeats": REPEATS, "scenes": {}}
    with tempfile.TemporaryDirectory(prefix="csr-res-") as tmp:
        tmp_path = Path(tmp)
        scenes = build_scenes("variant", 1, tmp_path / "ifc")
        for scene in scenes:
            out_dir = compile_usd(scene, tmp_path / "usd" / scene["scene_id"])
            for mode, filename in MODES:
                root = out_dir.with_name(filename)
                if not root.exists():
                    raise FileNotFoundError(f"missing compiled root: {root}")
                metrics = inspect_composition(root)
                timing = measure(root, REPEATS)
                scenario = scene["scene_id"].split("__")[0]
                rows.append({
                    "case_id": f"{scene['scene_id']}__{mode}",
                    "scenario": scenario,
                    "layer_condition": mode,
                    "active_prims": metrics["prim_count"],
                    "peak_cpu_mb": round(timing["peak_cpu_mb"], 3),
                    "peak_gpu_mb": 0,
                    "load_time_s": round(timing["load_time_s"], 6),
                    "collision_query_ms": "",
                })
                report["scenes"].setdefault(scene["scene_id"], {})[mode] = {
                    **{k: metrics[k] for k in (
                        "prim_count", "payload_prim_count", "rigid_body_count",
                        "collision_api_count", "used_layer_count", "used_layer_bytes",
                    )},
                    **timing,
                }
                print(f"{scene['scene_id']:<45}{mode:<16}"
                      f"prims={metrics['prim_count']:<5}load={timing['load_time_s']:.3f}s")

    RESULT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with RESULT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    report_dir = REPO / "generated" / "resource-efficiency" / args.run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(f"-> {RESULT_CSV} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
