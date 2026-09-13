"""Compare compiled scene semantics against generated fixture ground truth."""

from __future__ import annotations

from math import isclose
from typing import Any


def _safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def _set_f1(observed: set[tuple[Any, ...]], expected: set[tuple[Any, ...]]) -> dict:
    true_positive = len(observed & expected)
    precision = _safe_rate(true_positive, len(observed))
    recall = _safe_rate(true_positive, len(expected))
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positive": true_positive,
        "observed_count": len(observed),
        "expected_count": len(expected),
    }


def compare_scene_to_ground_truth(
    scene: dict[str, Any],
    truth: dict[str, Any],
) -> dict[str, Any]:
    """Compute source-preservation metrics with no simulator dependency."""

    observed_components = {
        item["id"]: item for item in scene.get("components", [])
    }
    expected_components = {
        item["id"]: item for item in truth.get("components", [])
    }
    shared_components = sorted(
        set(observed_components) & set(expected_components)
    )
    identity_matches = sum(
        observed_components[item_id].get("ifc_guid")
        == expected_components[item_id].get("ifc_guid")
        for item_id in shared_components
    )

    categorical_fields = (
        "ifc_class",
        "material",
        "workzone_id",
        "construction_state",
    )
    attribute_checks = 0
    attribute_matches = 0
    position_errors: list[float] = []
    dimension_errors: list[float] = []
    mass_relative_errors: list[float] = []
    for item_id in shared_components:
        observed = observed_components[item_id]
        expected = expected_components[item_id]
        for field in categorical_fields:
            attribute_checks += 1
            attribute_matches += observed.get(field) == expected.get(field)
        position_errors.extend(
            abs(float(left) - float(right))
            for left, right in zip(
                observed.get("position_m", []),
                expected.get("position_m", []),
            )
        )
        dimension_errors.extend(
            abs(float(left) - float(right))
            for left, right in zip(
                observed.get("dimensions_m", []),
                expected.get("dimensions_m", []),
            )
        )
        expected_mass = float(expected.get("mass_kg", 0.0))
        observed_mass = float(observed.get("mass_kg", 0.0))
        if expected_mass:
            mass_relative_errors.append(
                abs(observed_mass - expected_mass) / expected_mass
            )
        elif not isclose(observed_mass, expected_mass):
            mass_relative_errors.append(float("inf"))

    observed_interfaces = {
        (
            item.get("id"),
            item.get("component"),
            item.get("mate_component"),
            item.get("type"),
        )
        for item in scene.get("interfaces", [])
    }
    expected_interfaces = {
        (
            item.get("id"),
            item.get("component_id"),
            item.get("mate_component_id"),
            item.get("type"),
        )
        for item in truth.get("interfaces", [])
    }
    interface_metrics = _set_f1(observed_interfaces, expected_interfaces)

    observed_tasks = {
        (
            item.get("id"),
            item.get("actor"),
            item.get("target_component"),
            item.get("interface"),
            item.get("tool"),
        )
        for item in scene.get("tasks", [])
    }
    expected_tasks = {
        (
            item.get("id"),
            item.get("actor"),
            item.get("target_component"),
            item.get("interface_id"),
            item.get("tool_id"),
        )
        for item in truth.get("tasks", [])
    }
    task_metrics = _set_f1(observed_tasks, expected_tasks)

    return {
        "scene_id": scene.get("scene_id"),
        "component_id_recall": _safe_rate(
            len(shared_components), len(expected_components)
        ),
        "ifc_guid_accuracy": _safe_rate(
            identity_matches, len(expected_components)
        ),
        "categorical_attribute_accuracy": _safe_rate(
            attribute_matches, attribute_checks
        ),
        "interface_relation_precision": interface_metrics["precision"],
        "interface_relation_recall": interface_metrics["recall"],
        "interface_relation_f1": interface_metrics["f1"],
        "task_binding_precision": task_metrics["precision"],
        "task_binding_recall": task_metrics["recall"],
        "task_binding_f1": task_metrics["f1"],
        "max_position_error_m": max(position_errors, default=0.0),
        "max_dimension_error_m": max(dimension_errors, default=0.0),
        "max_mass_relative_error": max(mass_relative_errors, default=0.0),
    }
