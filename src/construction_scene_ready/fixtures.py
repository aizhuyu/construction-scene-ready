"""Generate small IFC4.3 assembly fixtures with machine-readable ground truth."""

from __future__ import annotations

import argparse
import json
import uuid
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ComponentSpec:
    component_id: str
    ifc_class: str
    name: str
    dimensions_m: tuple[float, float, float]
    position_m: tuple[float, float, float]
    mass_kg: float
    material: str
    workzone_id: str = "zone_a"


@dataclass(frozen=True)
class WorkZoneSpec:
    zone_id: str
    position_m: tuple[float, float, float]
    dimensions_m: tuple[float, float, float]
    active: bool
    interaction_lod: str

    @property
    def payload(self) -> str:
        return f"workzones/{self.zone_id}_payload.usda"


WORK_ZONES: tuple[WorkZoneSpec, ...] = (
    WorkZoneSpec(
        zone_id="zone_a",
        position_m=(1.0, 0.5, 0.0),
        dimensions_m=(3.0, 3.0, 2.6),
        active=True,
        interaction_lod="interface",
    ),
    WorkZoneSpec(
        zone_id="zone_b",
        position_m=(5.0, 0.5, 0.0),
        dimensions_m=(3.0, 3.0, 2.6),
        active=False,
        interaction_lod="workzone",
    ),
    WorkZoneSpec(
        zone_id="zone_c",
        position_m=(9.0, 0.5, 0.0),
        dimensions_m=(3.0, 3.0, 2.6),
        active=False,
        interaction_lod="workzone",
    ),
)


@dataclass(frozen=True)
class InterfaceSpec:
    interface_id: str
    component_id: str
    mate_component_id: str
    interface_type: str
    origin_m: tuple[float, float, float]
    axis: tuple[float, float, float]
    tolerance_mm: float


@dataclass(frozen=True)
class ToolSpec:
    tool_id: str
    asset_uri: str
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    task_type: str
    target_component: str
    interface_id: str
    required_capabilities: tuple[str, ...]
    preconditions: tuple[str, ...]
    success_criteria: tuple[str, ...]
    tool_id: str | None = None
    required_tool_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScenarioSpec:
    scene_id: str
    components: tuple[ComponentSpec, ...]
    interfaces: tuple[InterfaceSpec, ...]
    tasks: tuple[TaskSpec, ...]
    tools: tuple[ToolSpec, ...] = ()
    base_scene_id: str | None = None
    variant_parameters: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class VariantDesign:
    """Deterministic factors for controlled scene variation."""

    variant_index: int
    geometry_scale: float
    offset_x_m: float
    offset_y_m: float
    offset_z_m: float
    tolerance_scale: float

    @property
    def variant_id(self) -> str:
        return f"v{self.variant_index:03d}"

    def as_pairs(self) -> tuple[tuple[str, float], ...]:
        return (
            ("geometry_scale", self.geometry_scale),
            ("offset_x_m", self.offset_x_m),
            ("offset_y_m", self.offset_y_m),
            ("offset_z_m", self.offset_z_m),
            ("tolerance_scale", self.tolerance_scale),
        )


def scenario_specs() -> tuple[ScenarioSpec, ...]:
    gripper = ToolSpec(
        tool_id="g1_parallel_gripper",
        asset_uri="tools/g1_parallel_gripper.usd",
        capabilities=("grasp", "insertion"),
    )
    # === 钢结构梁柱节点组件 (基于真实建筑规范) ===
    # H型钢柱: HW200×200×8×12, 高度2.5m, 竖直
    steel_column = ComponentSpec(
        component_id="steel_column",
        ifc_class="IfcColumn",
        name="H-section steel column HW200x200",
        dimensions_m=(0.20, 0.20, 2.5),
        position_m=(2.0, 1.5, 1.25),
        mass_kg=78.5,
        material="Q345 steel",
    )
    # H型钢梁: HN300×150×6×9, 长0.6m, 从柱侧面水平伸出
    steel_beam = ComponentSpec(
        component_id="steel_beam",
        ifc_class="IfcBeam",
        name="H-section steel beam HN300x150",
        dimensions_m=(0.6, 0.15, 0.15),
        position_m=(2.35, 1.5, 1.0),
        mass_kg=8.9,
        material="Q345 steel",
    )
    # 连接板: 贴在柱侧面, 梁柱交接处, 带螺栓孔(孔在编译器里实现)
    plate = ComponentSpec(
        component_id="connection_plate",
        ifc_class="IfcPlate",
        name="Light-steel connection plate",
        dimensions_m=(0.20, 0.02, 0.25),
        position_m=(2.11, 1.5, 1.0),
        mass_kg=1.20,
        material="S235 steel",
    )
    member = ComponentSpec(
        component_id="steel_member",
        ifc_class="IfcMember",
        name="Light-steel frame member",
        dimensions_m=(1.80, 0.08, 0.08),
        position_m=(2.00, 1.50, 1.00),
        mass_kg=2.70,
        material="S235 steel",
    )
    pin = ComponentSpec(
        component_id="assembly_pin",
        ifc_class="IfcMechanicalFastener",
        name="Simplified assembly pin",
        dimensions_m=(0.10, 0.018, 0.018),
        position_m=(1.0, 1.5, 0.85),
        mass_kg=0.18,
        material="steel",
    )
    context_member_b = ComponentSpec(
        component_id="future_member_b",
        ifc_class="IfcMember",
        name="Future work-zone member B",
        dimensions_m=(1.50, 0.08, 0.08),
        position_m=(6.00, 1.50, 1.00),
        mass_kg=2.20,
        material="S235 steel",
        workzone_id="zone_b",
    )
    context_member_c = ComponentSpec(
        component_id="future_member_c",
        ifc_class="IfcMember",
        name="Future work-zone member C",
        dimensions_m=(1.20, 0.08, 0.08),
        position_m=(10.00, 1.50, 1.00),
        mass_kg=1.80,
        material="S235 steel",
        workzone_id="zone_c",
    )
    plate_interface = InterfaceSpec(
        interface_id="plate_member_alignment",
        component_id="connection_plate",
        mate_component_id="steel_member",
        interface_type="align",
        origin_m=(2.11, 1.5, 1.0),
        axis=(1.0, 0.0, 0.0),
        tolerance_mm=3.0,
    )
    pin_interface = InterfaceSpec(
        interface_id="plate_pin_insertion",
        component_id="connection_plate",
        mate_component_id="assembly_pin",
        interface_type="insert",
        origin_m=(2.11, 1.5, 1.0),
        axis=(1.0, 0.0, 0.0),
        tolerance_mm=2.0,
    )
    return (
        ScenarioSpec(
            scene_id="connection_plate_positioning",
            components=(steel_column, steel_beam, plate, member, context_member_b, context_member_c),
            interfaces=(plate_interface,),
            tasks=(
                TaskSpec(
                    task_id="position_plate",
                    task_type="align",
                    target_component="connection_plate",
                    interface_id="plate_member_alignment",
                    required_capabilities=("bimanual",),
                    preconditions=("steel_member_supported",),
                    success_criteria=("alignment_error_mm <= 3",),
                    tool_id="g1_parallel_gripper",
                    required_tool_capabilities=("grasp",),
                ),
            ),
            tools=(gripper,),
        ),
        ScenarioSpec(
            scene_id="pin_insertion",
            components=(steel_column, steel_beam, plate, pin, context_member_b, context_member_c),
            interfaces=(pin_interface,),
            tasks=(
                TaskSpec(
                    task_id="insert_pin",
                    task_type="insert",
                    target_component="connection_plate",
                    interface_id="plate_pin_insertion",
                    required_capabilities=("bimanual", "insertion"),
                    preconditions=("plate_aligned",),
                    success_criteria=("pin_depth_mm >= 25",),
                    tool_id="g1_parallel_gripper",
                    required_tool_capabilities=("insertion",),
                ),
            ),
            tools=(gripper,),
        ),
        ScenarioSpec(
            scene_id="sequential_assembly",
            components=(
                plate,
                member,
                pin,
                context_member_b,
                context_member_c,
            ),
            interfaces=(plate_interface, pin_interface),
            tasks=(
                TaskSpec(
                    task_id="position_plate",
                    task_type="align",
                    target_component="connection_plate",
                    interface_id="plate_member_alignment",
                    required_capabilities=("bimanual",),
                    preconditions=("steel_member_supported",),
                    success_criteria=("alignment_error_mm <= 3",),
                    tool_id="g1_parallel_gripper",
                    required_tool_capabilities=("grasp",),
                ),
                TaskSpec(
                    task_id="insert_pin",
                    task_type="insert",
                    target_component="connection_plate",
                    interface_id="plate_pin_insertion",
                    required_capabilities=("bimanual", "insertion"),
                    preconditions=("plate_aligned",),
                    success_criteria=("pin_depth_mm >= 25",),
                    tool_id="g1_parallel_gripper",
                    required_tool_capabilities=("insertion",),
                ),
            ),
            tools=(gripper,),
        ),
    )


def _van_der_corput(index: int, base: int) -> float:
    """Return one deterministic low-discrepancy sample in [0, 1)."""

    value = 0.0
    denominator = 1.0
    while index:
        index, remainder = divmod(index, base)
        denominator *= base
        value += remainder / denominator
    return value


def variant_designs(count: int) -> tuple[VariantDesign, ...]:
    """Create a reproducible, bounded design without a random-number state."""

    if count < 1:
        raise ValueError("count shall be at least one")
    designs = [
        VariantDesign(
            variant_index=0,
            geometry_scale=1.0,
            offset_x_m=0.0,
            offset_y_m=0.0,
            offset_z_m=0.0,
            tolerance_scale=1.0,
        )
    ]
    for index in range(1, count):
        designs.append(
            VariantDesign(
                variant_index=index,
                geometry_scale=round(
                    0.90 + 0.20 * _van_der_corput(index, 2), 6
                ),
                offset_x_m=round(
                    -0.15 + 0.30 * _van_der_corput(index, 3), 6
                ),
                offset_y_m=round(
                    -0.15 + 0.30 * _van_der_corput(index, 5), 6
                ),
                offset_z_m=round(
                    -0.05 + 0.10 * _van_der_corput(index, 7), 6
                ),
                tolerance_scale=round(
                    0.75 + 0.50 * _van_der_corput(index, 11), 6
                ),
            )
        )
    return tuple(designs)


def apply_variant(spec: ScenarioSpec, design: VariantDesign) -> ScenarioSpec:
    """Apply one controlled design while preserving material density."""

    scale = design.geometry_scale
    offset = (design.offset_x_m, design.offset_y_m, design.offset_z_m)
    components = tuple(
        replace(
            component,
            dimensions_m=tuple(
                round(value * scale, 9) for value in component.dimensions_m
            ),
            position_m=tuple(
                round(value + delta, 9)
                for value, delta in zip(component.position_m, offset)
            ),
            mass_kg=round(component.mass_kg * scale**3, 9),
        )
        for component in spec.components
    )
    interfaces = tuple(
        replace(
            interface,
            origin_m=tuple(
                round(value + delta, 9)
                for value, delta in zip(interface.origin_m, offset)
            ),
            tolerance_mm=round(
                interface.tolerance_mm * design.tolerance_scale, 9
            ),
        )
        for interface in spec.interfaces
    )
    return replace(
        spec,
        scene_id=f"{spec.scene_id}__{design.variant_id}",
        components=components,
        interfaces=interfaces,
        base_scene_id=spec.scene_id,
        variant_parameters=design.as_pairs(),
    )


def scenario_variant_specs(
    variants_per_scenario: int,
) -> tuple[ScenarioSpec, ...]:
    """Expand every base scenario using the same paired factor design."""

    designs = variant_designs(variants_per_scenario)
    return tuple(
        apply_variant(spec, design)
        for spec in scenario_specs()
        for design in designs
    )


def _matrix(position: tuple[float, float, float]) -> Any:
    import numpy as np

    matrix = np.identity(4)
    matrix[:3, 3] = position
    return matrix


def _stable_ifc_guid(key: str) -> str:
    """Return a deterministic IFC-compressed UUID for a semantic fixture key."""

    import ifcopenshell.guid

    value = uuid.uuid5(uuid.NAMESPACE_URL, f"construction-scene-ready:{key}")
    return ifcopenshell.guid.compress(value.hex)


def _stabilize_ifc_metadata(model: Any, scene_id: str) -> None:
    """Remove timestamps, random GUIDs, and set-order noise from test fixtures."""

    model.header.file_name.name = f"{scene_id}.ifc"
    model.header.file_name.time_stamp = "2000-01-01T00:00:00+00:00"

    occurrences: Counter[tuple[str, str]] = Counter()
    for entity in sorted(model.by_type("IfcRoot"), key=lambda item: item.id()):
        identity = (entity.is_a(), str(getattr(entity, "Name", "") or ""))
        ordinal = occurrences[identity]
        occurrences[identity] += 1
        entity.GlobalId = _stable_ifc_guid(
            f"{scene_id}:{identity[0]}:{identity[1]}:{ordinal}"
        )

    assignments = model.by_type("IfcUnitAssignment")
    if assignments:
        assignments[0].Units = tuple(
            sorted(
                assignments[0].Units,
                key=lambda unit: (
                    str(getattr(unit, "UnitType", "") or ""),
                    str(getattr(unit, "Prefix", "") or ""),
                    unit.id(),
                ),
            )
        )

    for relation_type, attribute in (
        ("IfcRelAggregates", "RelatedObjects"),
        ("IfcRelContainedInSpatialStructure", "RelatedElements"),
        ("IfcRelDefinesByProperties", "RelatedObjects"),
    ):
        for relation in model.by_type(relation_type):
            values = getattr(relation, attribute)
            setattr(
                relation,
                attribute,
                tuple(
                    sorted(
                        values,
                        key=lambda item: (
                            str(getattr(item, "GlobalId", "") or ""),
                            item.id(),
                        ),
                    )
                ),
            )


def _add_box(
    model: Any,
    body: Any,
    storey: Any,
    component: ComponentSpec,
) -> Any:
    import ifcopenshell.api.geometry
    import ifcopenshell.api.pset
    import ifcopenshell.api.root
    import ifcopenshell.api.spatial

    product = ifcopenshell.api.root.create_entity(
        model,
        ifc_class=component.ifc_class,
        name=component.name,
    )
    length, width, height = component.dimensions_m
    representation = ifcopenshell.api.geometry.add_wall_representation(
        model,
        context=body,
        length=length,
        thickness=width,
        height=height,
    )
    ifcopenshell.api.geometry.assign_representation(
        model, product=product, representation=representation
    )
    ifcopenshell.api.geometry.edit_object_placement(
        model,
        product=product,
        matrix=_matrix(component.position_m),
        is_si=True,
    )
    ifcopenshell.api.spatial.assign_container(
        model, products=[product], relating_structure=storey
    )
    pset = ifcopenshell.api.pset.add_pset(
        model, product=product, name="Pset_CSR_Component"
    )
    ifcopenshell.api.pset.edit_pset(
        model,
        pset=pset,
        properties={
            "ComponentId": component.component_id,
            "MassKg": component.mass_kg,
            "MaterialName": component.material,
            "LengthM": length,
            "WidthM": width,
            "HeightM": height,
            "WorkZoneId": component.workzone_id,
            "ConstructionState": "uninstalled",
        },
    )
    return product


def generate_fixture(spec: ScenarioSpec, output_dir: Path) -> tuple[Path, Path]:
    """Generate an IFC file and a sidecar with exact expected semantics."""

    import ifcopenshell.api.aggregate
    import ifcopenshell.api.context
    import ifcopenshell.api.geometry
    import ifcopenshell.api.project
    import ifcopenshell.api.pset
    import ifcopenshell.api.root
    import ifcopenshell.api.spatial
    import ifcopenshell.api.unit

    output_dir.mkdir(parents=True, exist_ok=True)
    model = ifcopenshell.api.project.create_file(version="IFC4X3")
    project = ifcopenshell.api.root.create_entity(
        model, ifc_class="IfcProject", name=f"CSR {spec.scene_id}"
    )
    ifcopenshell.api.unit.assign_unit(model)
    context = ifcopenshell.api.context.add_context(model, context_type="Model")
    body = ifcopenshell.api.context.add_context(
        model,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=context,
    )

    site = ifcopenshell.api.root.create_entity(
        model, ifc_class="IfcSite", name="Research site"
    )
    building = ifcopenshell.api.root.create_entity(
        model, ifc_class="IfcBuilding", name="Assembly benchmark building"
    )
    storey = ifcopenshell.api.root.create_entity(
        model, ifc_class="IfcBuildingStorey", name="Assembly floor"
    )
    ifcopenshell.api.aggregate.assign_object(
        model, products=[site], relating_object=project
    )
    ifcopenshell.api.aggregate.assign_object(
        model, products=[building], relating_object=site
    )
    ifcopenshell.api.aggregate.assign_object(
        model, products=[storey], relating_object=building
    )

    for workzone in WORK_ZONES:
        zone = ifcopenshell.api.root.create_entity(
            model,
            ifc_class="IfcSpace",
            name=f"Assembly work zone {workzone.zone_id}",
        )
        length, width, height = workzone.dimensions_m
        zone_representation = ifcopenshell.api.geometry.add_wall_representation(
            model,
            context=body,
            length=length,
            thickness=width,
            height=height,
        )
        ifcopenshell.api.geometry.assign_representation(
            model, product=zone, representation=zone_representation
        )
        ifcopenshell.api.geometry.edit_object_placement(
            model,
            product=zone,
            matrix=_matrix(workzone.position_m),
            is_si=True,
        )
        ifcopenshell.api.aggregate.assign_object(
            model, products=[zone], relating_object=storey
        )
        zone_pset = ifcopenshell.api.pset.add_pset(
            model, product=zone, name="Pset_CSR_WorkZone"
        )
        ifcopenshell.api.pset.edit_pset(
            model,
            pset=zone_pset,
            properties={
                "WorkZoneId": workzone.zone_id,
                "Active": workzone.active,
                "Payload": workzone.payload,
                "InteractionLOD": workzone.interaction_lod,
            },
        )

    products = {
        component.component_id: _add_box(model, body, storey, component)
        for component in spec.components
    }
    for interface in spec.interfaces:
        product = products[interface.component_id]
        pset = ifcopenshell.api.pset.add_pset(
            model,
            product=product,
            name=f"Pset_CSR_Interface_{interface.interface_id}",
        )
        ifcopenshell.api.pset.edit_pset(
            model,
            pset=pset,
            properties={
                "InterfaceId": interface.interface_id,
                "InterfaceType": interface.interface_type,
                "MateComponentId": interface.mate_component_id,
                "OriginX": interface.origin_m[0],
                "OriginY": interface.origin_m[1],
                "OriginZ": interface.origin_m[2],
                "AxisX": interface.axis[0],
                "AxisY": interface.axis[1],
                "AxisZ": interface.axis[2],
                "ToleranceMm": interface.tolerance_mm,
            },
        )

    for task_spec in spec.tasks:
        task = ifcopenshell.api.root.create_entity(
            model, ifc_class="IfcTask", name=task_spec.task_id
        )
        pset = ifcopenshell.api.pset.add_pset(
            model, product=task, name="Pset_CSR_Task"
        )
        ifcopenshell.api.pset.edit_pset(
            model,
            pset=pset,
            properties={
                "TaskId": task_spec.task_id,
                "TaskType": task_spec.task_type,
                "Actor": "unitree_g1",
                "TargetComponent": task_spec.target_component,
                "InterfaceId": task_spec.interface_id,
                "ToolId": task_spec.tool_id or "",
                "RequiredToolCapabilities": json.dumps(
                    task_spec.required_tool_capabilities
                ),
                "RequiredCapabilities": json.dumps(
                    task_spec.required_capabilities
                ),
                "Preconditions": json.dumps(task_spec.preconditions),
                "SuccessCriteria": json.dumps(task_spec.success_criteria),
            },
        )

    for tool_spec in spec.tools:
        tool = ifcopenshell.api.root.create_entity(
            model,
            ifc_class="IfcConstructionEquipmentResource",
            name=tool_spec.tool_id,
        )
        pset = ifcopenshell.api.pset.add_pset(
            model, product=tool, name="Pset_CSR_Tool"
        )
        ifcopenshell.api.pset.edit_pset(
            model,
            pset=pset,
            properties={
                "ToolId": tool_spec.tool_id,
                "AssetUri": tool_spec.asset_uri,
                "Capabilities": json.dumps(tool_spec.capabilities),
            },
        )

    project_pset = ifcopenshell.api.pset.add_pset(
        model, product=project, name="Pset_CSR_Scene"
    )
    ifcopenshell.api.pset.edit_pset(
        model,
        pset=project_pset,
        properties={
            "SceneId": spec.scene_id,
            "RobotId": "unitree_g1",
            "RobotCapabilities": json.dumps(
                ("bimanual", "insertion", "locomotion")
            ),
        },
    )

    _stabilize_ifc_metadata(model, spec.scene_id)
    ifc_path = output_dir / f"{spec.scene_id}.ifc"
    model.write(ifc_path)
    ground_truth = {
        "scene_id": spec.scene_id,
        "base_scene_id": spec.base_scene_id or spec.scene_id,
        "variant_parameters": dict(spec.variant_parameters),
        "components": [
            {
                "id": item.component_id,
                "ifc_guid": products[item.component_id].GlobalId,
                "ifc_class": item.ifc_class,
                "name": item.name,
                "dimensions_m": item.dimensions_m,
                "position_m": item.position_m,
                "mass_kg": item.mass_kg,
                "material": item.material,
                "workzone_id": item.workzone_id,
                "construction_state": "uninstalled",
            }
            for item in spec.components
        ],
        "interfaces": [
            {
                "id": item.interface_id,
                "component_id": item.component_id,
                "mate_component_id": item.mate_component_id,
                "type": item.interface_type,
                "origin_m": item.origin_m,
                "axis": item.axis,
                "tolerance_mm": item.tolerance_mm,
            }
            for item in spec.interfaces
        ],
        "workzones": [
            {
                "id": item.zone_id,
                "active": item.active,
                "payload": item.payload,
                "interaction_lod": item.interaction_lod,
            }
            for item in WORK_ZONES
        ],
        "robot": {
            "id": "unitree_g1",
            "capabilities": ["bimanual", "insertion", "locomotion"],
        },
        "tools": [
            {
                "id": item.tool_id,
                "asset_uri": item.asset_uri,
                "capabilities": item.capabilities,
            }
            for item in spec.tools
        ],
        "tasks": [
            {
                "id": item.task_id,
                "type": item.task_type,
                "actor": "unitree_g1",
                "target_component": item.target_component,
                "interface_id": item.interface_id,
                "tool_id": item.tool_id,
                "required_tool_capabilities": item.required_tool_capabilities,
                "required_capabilities": item.required_capabilities,
                "preconditions": item.preconditions,
                "success_criteria": item.success_criteria,
            }
            for item in spec.tasks
        ],
    }
    truth_path = output_dir / f"{spec.scene_id}.ground-truth.json"
    truth_path.write_text(
        json.dumps(ground_truth, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return ifc_path, truth_path


def generate_all(output_dir: Path) -> list[tuple[Path, Path]]:
    return [generate_fixture(spec, output_dir) for spec in scenario_specs()]


def generate_variant_suite(
    output_dir: Path,
    variants_per_scenario: int,
) -> list[tuple[Path, Path]]:
    return [
        generate_fixture(spec, output_dir)
        for spec in scenario_variant_specs(variants_per_scenario)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("generated/ifc"),
    )
    parser.add_argument(
        "--variants-per-scenario",
        type=int,
        default=0,
        help="Generate a controlled variant suite instead of three base scenes.",
    )
    args = parser.parse_args()
    generated = (
        generate_variant_suite(args.output_dir, args.variants_per_scenario)
        if args.variants_per_scenario
        else generate_all(args.output_dir)
    )
    for ifc_path, truth_path in generated:
        print(ifc_path)
        print(truth_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
