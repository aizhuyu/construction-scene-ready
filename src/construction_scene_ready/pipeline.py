"""Run the complete CPU-first IFC-to-OpenUSD research pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import save_benchmark
from .cewg import build_cewg, check_graph_integrity
from .fault_injection import generate_fault_set
from .fixtures import generate_all
from .ground_truth import compare_scene_to_ground_truth
from .ifc_parser import compile_ifc
from .usd_compiler import compile_usd
from .usd_metrics import compare_compositions
from .validator import SceneValidator


def run_pipeline(output_dir: Path) -> dict:
    ifc_dir = output_dir / "ifc"
    scene_dir = output_dir / "scenes"
    cewg_dir = output_dir / "cewg"
    usd_dir = output_dir / "usd"
    fault_dir = output_dir / "faults"
    report_dir = output_dir / "reports"
    for directory in (scene_dir, cewg_dir, usd_dir, fault_dir, report_dir):
        directory.mkdir(parents=True, exist_ok=True)

    validator = SceneValidator()
    summary = {"scenes": []}
    compiled_scenes = []
    preservation_metrics = []
    composition_metrics = []
    for ifc_path, truth_path in generate_all(ifc_dir):
        scene = compile_ifc(ifc_path)
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        preservation = compare_scene_to_ground_truth(scene, truth)
        preservation_metrics.append(preservation)
        compiled_scenes.append(scene)
        scene_path = scene_dir / f"{scene['scene_id']}.json"
        scene_path.write_text(
            json.dumps(scene, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        cewg = build_cewg(scene)
        graph_errors = check_graph_integrity(cewg)
        if graph_errors:
            raise ValueError(
                f"CEWG integrity failed for {scene['scene_id']}: {graph_errors}"
            )
        cewg_path = cewg_dir / f"{scene['scene_id']}.cewg.json"
        cewg_path.write_text(
            json.dumps(cewg, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        report = validator.validate(scene)
        report_path = report_dir / f"{scene['scene_id']}.validation.json"
        report_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        root_usd = compile_usd(scene, usd_dir / scene["scene_id"])
        all_loaded_usd = root_usd.with_name("building_root_all_loaded.usda")
        composition = compare_compositions(root_usd, all_loaded_usd)
        composition["scene_id"] = scene["scene_id"]
        composition_metrics.append(composition)
        fault_reports = []
        for candidate in generate_fault_set(scene):
            candidate_path = fault_dir / f"{candidate['scene_id']}.json"
            candidate_path.write_text(
                json.dumps(candidate, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            candidate_report = validator.validate(candidate)
            fault_reports.append(
                {
                    "fault": candidate["fault_ground_truth"]["fault"],
                    "passed": candidate_report.passed,
                    "rule_ids": sorted(
                        {item.rule_id for item in candidate_report.issues}
                    ),
                }
            )
        summary["scenes"].append(
            {
                "scene_id": scene["scene_id"],
                "ifc": str(ifc_path),
                "ground_truth": str(truth_path),
                "scene": str(scene_path),
                "cewg": str(cewg_path),
                "usd": str(root_usd),
                "usd_all_loaded": str(all_loaded_usd),
                "passed": report.passed,
                "faults": fault_reports,
            }
        )
    benchmark = save_benchmark(
        compiled_scenes, report_dir / "cpu-benchmark.json"
    )
    preservation_path = report_dir / "semantic-preservation.json"
    preservation_path.write_text(
        json.dumps(preservation_metrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    summary["cpu_benchmark"] = {
        key: value for key, value in benchmark.items() if key != "cases"
    }
    summary["semantic_preservation"] = preservation_metrics
    composition_path = report_dir / "usd-composition.json"
    composition_path.write_text(
        json.dumps(composition_metrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    summary["usd_composition"] = composition_metrics
    summary_path = output_dir / "pipeline-summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("generated/local-pipeline")
    )
    args = parser.parse_args()
    summary = run_pipeline(args.output_dir)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
