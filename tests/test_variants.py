from __future__ import annotations

from construction_scene_ready.fixtures import (
    apply_variant,
    scenario_specs,
    scenario_variant_specs,
    variant_designs,
)


def test_variant_design_is_deterministic_and_bounded() -> None:
    first = variant_designs(12)
    second = variant_designs(12)

    assert first == second
    assert first[0].geometry_scale == 1.0
    assert first[0].tolerance_scale == 1.0
    assert all(0.90 <= item.geometry_scale <= 1.10 for item in first)
    assert all(0.75 <= item.tolerance_scale <= 1.25 for item in first)
    assert len({item.as_pairs() for item in first}) == len(first)


def test_variant_preserves_density_and_records_design() -> None:
    base = scenario_specs()[0]
    design = variant_designs(2)[1]
    variant = apply_variant(base, design)

    base_component = base.components[0]
    varied_component = variant.components[0]
    scale = design.geometry_scale
    assert varied_component.mass_kg == round(
        base_component.mass_kg * scale**3, 9
    )
    assert variant.base_scene_id == base.scene_id
    assert dict(variant.variant_parameters)["geometry_scale"] == scale
    assert variant.scene_id.endswith("__v001")


def test_variant_suite_is_paired_across_three_tasks() -> None:
    variants = scenario_variant_specs(4)
    assert len(variants) == 12
    assert {item.base_scene_id for item in variants} == {
        "connection_plate_positioning",
        "pin_insertion",
        "sequential_assembly",
    }
