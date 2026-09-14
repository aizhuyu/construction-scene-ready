#!/usr/bin/env python3
"""R5 scale check: resource effect of task-activated composition as the
number of work zones grows (1, 5, 10, 20 zones, 4 components each).

Synthesizes valid scene dicts (same schema as examples/minimal_scene.json)
with K work zones, one active; compiles both composition roots and measures
active prims, layer bytes, and cold load time (5 fresh-tree opens per mode).
Appends rows to data/results/resource_efficiency.csv (registered schema).
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from construction_scene_ready.usd_compiler import compile_usd  # noqa: E402
from construction_scene_ready.usd_metrics import inspect_composition  # noqa: E402

RESULT_CSV = REPO / "data" / "results" / "resource_efficiency.csv"
CSV_FIELDS = (
    "case_id", "scenario", "layer_condition", "active_prims", "peak_cpu_mb",
    "peak_gpu_mb", "load_time_s", "collision_query_ms",
)
ZONE_COUNTS = (1, 5, 10, 20)
COMPONENTS_PER_ZONE = 4
REPEATS = 5

MEASURE_SNIPPET = """
import json, resource, shutil, sys, tempfile
from pathlib import Path
from time import perf_counter
from pxr import Usd

root = Path(sys.argv[1]); repeats = int(sys.argv[2]); times = []
for i in range(repeats):
    with tempfile.TemporaryDirectory() as tmp:
        copied = Path(tmp) / "tree"
        shutil.copytree(root.parent, copied)
        start = perf_counter()
        stage = Usd.Stage.Open(str(copied / root.name), Usd.Stage.LoadAll)
        _ = list(stage.Traverse())
        times.append(perf_counter() - start)
        del stage
times.sort()
print(json.dumps({"load_time_s": times[len(times)//2]}))
"""


def make_scene(k: int) -> dict:
    zones, components = [], []
    for zi in range(k):
        zid = f"zone_{zi:02d}"
        zones.append({
            "id": zid, "active": zi == 0,
            "payload": f"workzones/{zid}_payload.usda",
            "interaction_lod": "interface",
        })
        for ci in range(COMPONENTS_PER_ZONE):
            components.append({
                "id": f"member_{zi:02d}_{ci}",
                "ifc_guid": f"scale{zi:02d}{ci:02d}scale{zi:02d}{ci:02d}000{zi}{ci}",
                "ifc_class": "IfcMember",
                "mass_kg": 10.0 + zi + ci,
                "construction_state": "aligned",
                "workzone_id": zid,
                "position_m": [zi * 3.0, ci * 1.0, 1.0],
                "dimensions_m": [0.3, 0.3, 2.0],
            })
    return {
        "scene_id": f"scale_{k}zones",
        "schema_version": "0.2.0",
        "coordinate_system": {"up_axis": "Z", "meters_per_unit": 1.0},
        "components": components,
        "interfaces": [],
        "robots": [],
        "tools": [],
        "workzones": zones,
        "tasks": [],
        "provenance": [
            {"entity": c["id"], "property": "mass_kg", "value": c["mass_kg"],
             "source": "synthetic-scale-fixture", "source_type": "measured",
             "unit": "kg", "confidence": 1.0, "uncertainty_interval": [c["mass_kg"], c["mass_kg"]],
             "authority_level": 1, "auto_repair_allowed": True,
             "requires_human_confirmation_for_deployment": False}
            for c in components
        ],
    }


def main() -> int:
    rows = []
    summary = []
    with tempfile.TemporaryDirectory(prefix="csr-scale-") as tmp:
        tmp_path = Path(tmp)
        for k in ZONE_COUNTS:
            scene = make_scene(k)
            out_dir = compile_usd(scene, tmp_path / f"scale_{k}")
            for mode, fname in (("task_activated", "building_root.usda"),
                                ("all_loaded", "building_root_all_loaded.usda")):
                root = out_dir.with_name(fname)
                metrics = inspect_composition(root)
                timing = json.loads(subprocess.run(
                    [sys.executable, "-c", MEASURE_SNIPPET, str(root), str(REPEATS)],
                    capture_output=True, text=True, check=True,
                ).stdout.strip().splitlines()[-1])
                rows.append({
                    "case_id": f"scale_{k}zones__{mode}",
                    "scenario": f"scale_{k}zones",
                    "layer_condition": mode,
                    "active_prims": metrics["prim_count"],
                    "peak_cpu_mb": 0,
                    "peak_gpu_mb": 0,
                    "load_time_s": round(timing["load_time_s"], 6),
                    "collision_query_ms": "",
                })
                summary.append({"k": k, "mode": mode,
                                "prims": metrics["prim_count"],
                                "bytes": metrics["used_layer_bytes"],
                                "load_s": timing["load_time_s"]})
                print(f"K={k:<3}{mode:<16}prims={metrics['prim_count']:<5}"
                      f"bytes={metrics['used_layer_bytes']:<8}load={timing['load_time_s']*1000:.1f}ms",
                      flush=True)

    existing = list(csv.DictReader(RESULT_CSV.open(encoding="utf-8")))
    with RESULT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(existing + rows)
    report = REPO / "generated" / "resource-efficiency" / "scale-report.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"appended {len(rows)} rows -> {RESULT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
