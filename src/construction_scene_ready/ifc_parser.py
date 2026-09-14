"""Compile CSR-enriched IFC4.3 fixtures into the scene intermediate model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _first_pset(psets: dict[str, Any], prefix: str) -> list[dict[str, Any]]:
    return [
        {"name": name, "properties": values}
        for name, values in psets.items()
        if name.startswith(prefix)
    ]


def _decode_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    try:
        loaded = json.loads(str(value))
    except json.JSONDecodeError:
        return [str(value)]
    return [str(item) for item in loaded]


def compile_ifc(ifc_path: Path) -> dict[str, Any]:
    import ifcopenshell
    import ifcopenshell.util.element
    import ifcopenshell.util.placement
    import ifcopenshell.util.unit

    model = ifcopenshell.open(ifc_path)
    length_unit_scale = float(ifcopenshell.util.unit.calculate_unit_scale(model))
    project = model.by_type("IfcProject")[0]
    project_psets = ifcopenshell.util.element.get_psets(project)
    scene_pset = project_psets.get("Pset_CSR_Scene", {})
    scene_id = str(scene_pset.get("SceneId") or ifc_path.stem)

    components: list[dict[str, Any]] = []
    interfaces: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    for element in model.by_type("IfcElement"):
        psets = ifcopenshell.util.element.get_psets(element)
        component_pset = psets.get("Pset_CSR_Component")
        if not component_pset:
            continue
        component_id = str(component_pset["ComponentId"])
        matrix = ifcopenshell.util.placement.get_local_placement(
            element.ObjectPlacement
        )
        dimensions = [
            float(component_pset["LengthM"]),
            float(component_pset["WidthM"]),
            float(component_pset["HeightM"]),
        ]
        mass_kg = float(component_pset["MassKg"])
        components.append(
            {
                "id": component_id,
                "ifc_guid": element.GlobalId,
                "ifc_class": element.is_a(),
                "name": element.Name,
                "dimensions_m": dimensions,
                "position_m": [
                    float(value) * length_unit_scale
                    for value in matrix[:3, 3]
                ],
                "mass_kg": mass_kg,
                "material": str(component_pset["MaterialName"]),
                "workzone_id": str(component_pset["WorkZoneId"]),
                "construction_state": str(
                    component_pset["ConstructionState"]
                ),
            }
        )
        provenance.append(
            {
                "entity": component_id,
                "property": "mass_kg",
                "source": "ifc_pset",
                "source_type": "explicit_ifc",
                "value": mass_kg,
                "unit": "kg",
                "confidence": 1.0,
                "uncertainty_interval": [mass_kg, mass_kg],
                "authority_level": 3,
                "auto_repair_allowed": False,
            }
        )
        for record in _first_pset(psets, "Pset_CSR_Interface_"):
            values = record["properties"]
            interface_id = str(values["InterfaceId"])
            tolerance = float(values["ToleranceMm"])
            interfaces.append(
                {
                    "id": interface_id,
                    "component": component_id,
                    "mate_component": str(values["MateComponentId"]),
                    "type": str(values["InterfaceType"]),
                    "origin_m": [
                        float(values["OriginX"]),
                        float(values["OriginY"]),
                        float(values["OriginZ"]),
                    ],
                    "axis": [
                        float(values["AxisX"]),
                        float(values["AxisY"]),
                        float(values["AxisZ"]),
                    ],
                    "tolerance_mm": tolerance,
                    # 契约 v0.3.0: 任务要求的最小间隙(默认=声明容差, 即自洽)
                    "required_clearance_mm": float(
                        values.get("RequiredClearanceMm") or tolerance
                    ),
                }
            )
            provenance.append(
                {
                    "entity": interface_id,
                    "property": "tolerance_mm",
                    "source": "ifc_interface_pset",
                    "source_type": "explicit_ifc",
                    "value": tolerance,
                    "unit": "mm",
                    "confidence": 1.0,
                    "uncertainty_interval": [tolerance, tolerance],
                    "authority_level": 3,
                    "auto_repair_allowed": False,
                }
            )
            # 契约 v0.3.0 (CSR-SCN-031): 接口原点证据记录
            provenance.append(
                {
                    "entity": interface_id,
                    "property": "origin_m",
                    "source": "ifc_interface_pset",
                    "source_type": "explicit_ifc",
                    "value": [
                        float(values["OriginX"]),
                        float(values["OriginY"]),
                        float(values["OriginZ"]),
                    ],
                    "unit": "m",
                    "confidence": 1.0,
                    "uncertainty_interval": [
                        [float(values["OriginX"]), float(values["OriginY"]), float(values["OriginZ"])],
                        [float(values["OriginX"]), float(values["OriginY"]), float(values["OriginZ"])],
                    ],
                    "authority_level": 3,
                    "auto_repair_allowed": False,
                }
            )

    workzones: list[dict[str, Any]] = []
    for space in model.by_type("IfcSpace"):
        values = ifcopenshell.util.element.get_psets(space).get(
            "Pset_CSR_WorkZone"
        )
        if not values:
            continue
        workzones.append(
            {
                "id": str(values["WorkZoneId"]),
                "active": bool(values["Active"]),
                "payload": str(values["Payload"]),
                "interaction_lod": str(values["InteractionLOD"]),
            }
        )

    tasks: list[dict[str, Any]] = []
    for task in model.by_type("IfcTask"):
        values = ifcopenshell.util.element.get_psets(task).get("Pset_CSR_Task")
        if not values:
            continue
        tasks.append(
            {
                "id": str(values["TaskId"]),
                "type": str(values["TaskType"]),
                "actor": str(values["Actor"]),
                "target_component": str(values["TargetComponent"]),
                "interface": str(values["InterfaceId"]),
                "tool": str(values.get("ToolId") or ""),
                "required_tool_capabilities": _decode_list(
                    values.get("RequiredToolCapabilities")
                ),
                "required_capabilities": _decode_list(
                    values["RequiredCapabilities"]
                ),
                "preconditions": _decode_list(values["Preconditions"]),
                "success_criteria": _decode_list(values["SuccessCriteria"]),
            }
        )

    tools: list[dict[str, Any]] = []
    for resource in model.by_type("IfcConstructionEquipmentResource"):
        values = ifcopenshell.util.element.get_psets(resource).get(
            "Pset_CSR_Tool"
        )
        if not values:
            continue
        tools.append(
            {
                "id": str(values["ToolId"]),
                "asset_uri": str(values["AssetUri"]),
                "capabilities": _decode_list(values["Capabilities"]),
            }
        )

    robot_id = str(scene_pset.get("RobotId") or "unitree_g1")
    robot_capabilities = _decode_list(scene_pset.get("RobotCapabilities"))
    provenance.append(
        {
            "entity": "default_steel_contact",
            "property": "friction",
            "source": "benchmark_protocol:steel_contact_v0.1",
            "source_type": "controlled_benchmark_assumption",
            "value": 0.5,
            "unit": "dimensionless",
            "confidence": 0.5,
            "uncertainty_interval": [0.3, 0.7],
            "authority_level": 1,
            "auto_repair_allowed": False,
            "requires_human_confirmation_for_deployment": True,
        }
    )
    return {
        "schema_version": "0.2.0",
        "scene_id": scene_id,
        "source_ifc": ifc_path.name,
        "coordinate_system": {"up_axis": "Z", "meters_per_unit": 1.0},
        "components": sorted(components, key=lambda item: item["id"]),
        "interfaces": sorted(interfaces, key=lambda item: item["id"]),
        "robots": [
            {
                "id": robot_id,
                "asset_uri": "robots/unitree_g1.usd",
                "capabilities": robot_capabilities,
            }
        ],
        "tools": sorted(tools, key=lambda item: item["id"]),
        "workzones": sorted(workzones, key=lambda item: item["id"]),
        "tasks": sorted(tasks, key=lambda item: item["id"]),
        "provenance": provenance,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ifc", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    scene = compile_ifc(args.ifc)
    payload = json.dumps(scene, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
