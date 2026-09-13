"""CPU benchmark for validation and validator-grounded repair."""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter_ns
from typing import Any

from .fault_injection import generate_fault_set
from .repair import repair_scene
from .validator import SceneValidator


def run_cpu_benchmark(scenes: list[dict[str, Any]]) -> dict[str, Any]:
    validator = SceneValidator()
    cases: list[dict[str, Any]] = []
    true_positive = false_positive = false_negative = 0

    for scene in scenes:
        for faulty in generate_fault_set(scene):
            fault = faulty["fault_ground_truth"]["fault"]
            expected = set(faulty["fault_ground_truth"]["expected_rules"])
            start = perf_counter_ns()
            before = validator.validate(faulty)
            validation_ms = (perf_counter_ns() - start) / 1_000_000
            found = {issue.rule_id for issue in before.issues}
            true_positive += len(expected & found)
            false_negative += len(expected - found)
            false_positive += len(found - expected)

            start = perf_counter_ns()
            repaired, audit = repair_scene(faulty, scene, validator=validator)
            repair_ms = (perf_counter_ns() - start) / 1_000_000
            cases.append(
                {
                    "scene_id": scene["scene_id"],
                    "fault": fault,
                    "expected_rules": sorted(expected),
                    "observed_rules": sorted(found),
                    "validation_ms": round(validation_ms, 6),
                    "repair_ms": round(repair_ms, 6),
                    "repair_accepted": audit["accepted"],
                    "escalated": bool(audit["blocked_rule_ids"]),
                    "blocked_rule_ids": audit["blocked_rule_ids"],
                    "repair_events": audit["events"],
                    "repaired_scene_id": repaired["scene_id"],
                }
            )

    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 0.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 0.0
    )
    repair_successes = sum(case["repair_accepted"] for case in cases)
    escalations = sum(case["escalated"] for case in cases)
    return {
        "case_count": len(cases),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "repair_success_rate": repair_successes / len(cases) if cases else 0.0,
        "escalation_rate": escalations / len(cases) if cases else 0.0,
        "mean_validation_ms": sum(c["validation_ms"] for c in cases) / len(cases),
        "mean_repair_ms": sum(c["repair_ms"] for c in cases) / len(cases),
        "cases": cases,
    }


def save_benchmark(scenes: list[dict[str, Any]], output_path: Path) -> dict[str, Any]:
    result = run_cpu_benchmark(scenes)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return result
