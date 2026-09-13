from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("ifcopenshell") is None
    or importlib.util.find_spec("pxr") is None,
    reason="IFC and OpenUSD extras are not installed",
)


def test_task_activation_reduces_composed_stage(tmp_path: Path) -> None:
    from construction_scene_ready.fixtures import (
        generate_fixture,
        scenario_specs,
    )
    from construction_scene_ready.ifc_parser import compile_ifc
    from construction_scene_ready.usd_compiler import compile_usd
    from construction_scene_ready.usd_metrics import compare_compositions

    ifc_path, _ = generate_fixture(scenario_specs()[2], tmp_path / "ifc")
    scene = compile_ifc(ifc_path)
    active_root = compile_usd(scene, tmp_path / "usd")
    all_root = active_root.with_name("building_root_all_loaded.usda")
    metrics = compare_compositions(active_root, all_root)

    assert metrics["task_activated"]["composition_mode"] == "task_activated"
    assert metrics["all_loaded"]["composition_mode"] == "all_loaded"
    assert (
        metrics["task_activated"]["prim_count"]
        < metrics["all_loaded"]["prim_count"]
    )
    assert metrics["reduction"]["rigid_body_count"] > 0
    assert metrics["reduction"]["used_layer_bytes"] > 0

