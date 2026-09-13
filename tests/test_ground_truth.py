from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from construction_scene_ready.ground_truth import (
    compare_scene_to_ground_truth,
)


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("ifcopenshell") is None,
    reason="IfcOpenShell is not installed",
)


def test_compiled_fixture_preserves_generated_ground_truth(tmp_path: Path) -> None:
    from construction_scene_ready.fixtures import (
        generate_fixture,
        scenario_specs,
    )
    from construction_scene_ready.ifc_parser import compile_ifc

    ifc_path, truth_path = generate_fixture(scenario_specs()[2], tmp_path)
    scene = compile_ifc(ifc_path)
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    metrics = compare_scene_to_ground_truth(scene, truth)

    assert metrics["component_id_recall"] == 1.0
    assert metrics["ifc_guid_accuracy"] == 1.0
    assert metrics["categorical_attribute_accuracy"] == 1.0
    assert metrics["interface_relation_f1"] == 1.0
    assert metrics["task_binding_f1"] == 1.0
    assert metrics["max_position_error_m"] < 1e-12
    assert metrics["max_dimension_error_m"] < 1e-12
    assert metrics["max_mass_relative_error"] < 1e-12

