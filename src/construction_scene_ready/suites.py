"""Shared scene-suite construction for registered experiment runners."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fixtures import generate_fixture, scenario_specs, scenario_variant_specs
from .ifc_parser import compile_ifc


def build_scenes(scene_kind: str, variant_index: int, workdir: Path) -> list[dict[str, Any]]:
    """Compile the scene suite for one partition (base or one variant index)."""
    if scene_kind == "base":
        specs = list(scenario_specs())
    else:
        specs = [
            spec
            for spec in scenario_variant_specs(variant_index + 1)
            if spec.base_scene_id is not None
            and spec.scene_id.endswith(f"__v{variant_index:03d}")
        ]
    scenes = []
    for spec in specs:
        ifc_path, _truth = generate_fixture(spec, workdir)
        scenes.append(compile_ifc(ifc_path))
    return scenes
