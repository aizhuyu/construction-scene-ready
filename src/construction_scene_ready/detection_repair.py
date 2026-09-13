"""Registered detection/repair experiment runner (B0/B1 + deterministic ablations).

Implements the frozen protocol in docs/baseline-protocol.md for the methods
that do not require a language model:

- B0 ``direct-conversion``: compile once, no CSR rules.  Detection is limited
  to a generic structural check (top-level sections and types); it has no
  access to scene-readiness semantics and therefore cannot name rule findings.
- B1 ``fixed-rule-repair``: SceneValidator + the frozen rule-to-tool whitelist
  (repair.py), one fixed repair action per known rule.
- A1 ``ablation-no-provenance``: B1 with the provenance rule group disabled.
- A2 ``ablation-no-task-validator``: B1 with the task rule group disabled.
- A4 ``ablation-fixed-repair-order``: B1's repair pass applied in a fixed
  rule-id order.  The whitelist is one-to-one, so A4 is expected to coincide
  with B1; the ablation documents that agentic tool *selection* (B3) has no
  deterministic advantage on this fault set.

A3 (resource use) is reported separately in resource_efficiency.csv.
A5 (prose diagnostics) and B2/B3 require a frozen language-model endpoint and
remain registered as planned in docs/experiment-registry.csv.
"""

from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
from time import perf_counter_ns
from typing import Any

from .fault_injection import inject_fault
from .repair import repair_scene
from .validator import SceneValidator

METHODS: dict[str, dict[str, Any]] = {
    "direct-conversion": {"kind": "b0"},
    "fixed-rule-repair": {"kind": "b1"},
    "ablation-no-provenance": {"kind": "b1", "disabled_groups": ("provenance",)},
    "ablation-no-task-validator": {"kind": "b1", "disabled_groups": ("task",)},
    "ablation-fixed-repair-order": {"kind": "b1"},
}

CSV_FIELDS = (
    "run_id", "commit_sha", "partition", "scene_id", "fault_id", "fault_family",
    "method", "seed", "expected_rules", "observed_rules",
    "true_positive", "false_positive", "false_negative", "detected",
    "valid_repair", "incorrect_repair", "escalated",
    "validation_ms", "repair_ms",
)

#: Keys injected by fault tooling that are not part of the pristine scene.
_NON_SCENE_KEYS = ("fault_ground_truth",)


def generic_structural_check(scene: dict[str, Any]) -> list[str]:
    """B0's only detector: structural sanity, no construction semantics.

    Returns a list of human-readable structural problems (never rule ids).
    A direct IFC-to-USD style conversion can notice a malformed document but
    cannot know that, e.g., a task target must resolve to a component.
    """
    problems: list[str] = []
    for section in (
        "scene_id", "coordinate_system", "components", "workzones",
        "interfaces", "tasks", "robots", "tools", "provenance",
    ):
        if section not in scene:
            problems.append(f"missing top-level section: {section}")
    if "coordinate_system" in scene:
        for key in ("up_axis", "meters_per_unit"):
            if key not in scene["coordinate_system"]:
                problems.append(f"missing coordinate_system.{key}")
    return problems


def _scene_equivalent(
    candidate: dict[str, Any], reference: dict[str, Any]
) -> bool:
    """Semantic equivalence of a repaired scene against the pristine scene.

    Provenance records are keyed by (subject, property); their list order is
    not semantic, so provenance is canonicalized before comparison.  Lists
    with positional identity (components, interfaces, tasks, ...) stay
    order-sensitive.
    """
    left = {k: v for k, v in candidate.items() if k not in _NON_SCENE_KEYS}
    right = {k: v for k, v in reference.items() if k not in _NON_SCENE_KEYS}
    left = copy.deepcopy(left)
    right = copy.deepcopy(right)
    left["scene_id"] = right["scene_id"]
    for scene in (left, right):
        if isinstance(scene.get("provenance"), list):
            scene["provenance"] = sorted(
                scene["provenance"], key=lambda r: json.dumps(r, sort_keys=True)
            )
    return left == right


def run_case(
    scene: dict[str, Any],
    fault_id: str,
    fault_family: str,
    method: str,
    *,
    run_id: str,
    commit_sha: str,
    partition: str,
    seed: int,
) -> dict[str, Any]:
    """Run one faulted case under one method and return one tidy CSV row."""
    spec = METHODS[method]
    faulty = inject_fault(scene, fault_id)
    expected = set(faulty["fault_ground_truth"]["expected_rules"])

    if spec["kind"] == "b0":
        start = perf_counter_ns()
        generic_structural_check(faulty)
        validation_ms = (perf_counter_ns() - start) / 1_000_000
        found: set[str] = set()
        valid_repair = incorrect = escalated = False
        repair_ms = 0.0
    else:
        validator = SceneValidator(
            disabled_groups=spec.get("disabled_groups", ())
        )
        start = perf_counter_ns()
        before = validator.validate(faulty)
        validation_ms = (perf_counter_ns() - start) / 1_000_000
        found = {issue.rule_id for issue in before.issues}
        start = perf_counter_ns()
        repaired, audit = repair_scene(faulty, scene, validator=validator)
        repair_ms = (perf_counter_ns() - start) / 1_000_000
        escalated = bool(audit["blocked_rule_ids"])
        if audit["accepted"]:
            incorrect = not _scene_equivalent(repaired, scene)
            valid_repair = not incorrect
        else:
            valid_repair = incorrect = False

    true_positive = len(expected & found)
    return {
        "run_id": run_id,
        "commit_sha": commit_sha,
        "partition": partition,
        "scene_id": scene["scene_id"],
        "fault_id": fault_id,
        "fault_family": fault_family,
        "method": method,
        "seed": seed,
        "expected_rules": "|".join(sorted(expected)),
        "observed_rules": "|".join(sorted(found)),
        "true_positive": true_positive,
        "false_positive": len(found - expected),
        "false_negative": len(expected - found),
        "detected": int(expected <= found),
        "valid_repair": int(valid_repair),
        "incorrect_repair": int(incorrect),
        "escalated": int(escalated),
        "validation_ms": round(validation_ms, 6),
        "repair_ms": round(repair_ms, 6),
    }


def write_rows(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-method headline metrics (used by run reports)."""
    summary: dict[str, Any] = {}
    for method in METHODS:
        subset = [row for row in rows if row["method"] == method]
        if not subset:
            continue
        tp = sum(row["true_positive"] for row in subset)
        fp = sum(row["false_positive"] for row in subset)
        fn = sum(row["false_negative"] for row in subset)
        summary[method] = {
            "cases": len(subset),
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "detected_rate": sum(row["detected"] for row in subset) / len(subset),
            "valid_repair_rate": sum(row["valid_repair"] for row in subset) / len(subset),
            "incorrect_repair_rate": sum(row["incorrect_repair"] for row in subset) / len(subset),
            "escalation_rate": sum(row["escalated"] for row in subset) / len(subset),
            "mean_validation_ms": sum(row["validation_ms"] for row in subset) / len(subset),
            "mean_repair_ms": sum(row["repair_ms"] for row in subset) / len(subset),
        }
    return summary


def write_summary(summary: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
