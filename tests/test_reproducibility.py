from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from construction_scene_ready.pipeline import run_pipeline


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("ifcopenshell") is None
    or importlib.util.find_spec("pxr") is None,
    reason="IFC and OpenUSD extras are not installed",
)


def _scientific_outputs(root: Path) -> dict[str, bytes]:
    """Return deterministic source artefacts, excluding runtime measurements."""

    selected: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in {"reports/cpu-benchmark.json", "pipeline-summary.json"}:
            continue
        selected[relative] = path.read_bytes()
    return selected


def test_pipeline_source_artefacts_are_byte_reproducible(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    run_pipeline(first)
    run_pipeline(second)

    assert _scientific_outputs(first) == _scientific_outputs(second)
