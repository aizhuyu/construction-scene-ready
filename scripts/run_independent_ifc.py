#!/usr/bin/env python3
"""R4b: author an INDEPENDENT beam-plate-hole IFC (not from the fixture
generator), compile and validate it -> non-empty task-ready scene.

Proves an independently modeled case compiles end-to-end.
Writes generated/external-ifc-independent/report.json
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.placement
import ifcopenshell.guid

from construction_scene_ready.ifc_parser import compile_ifc
from construction_scene_ready.validator import SceneValidator

OUT = REPO / "generated" / "external-ifc-independent"
OUT.mkdir(parents=True, exist_ok=True)
IFC_PATH = OUT / "independent_beam_plate.ifc"


def pset(model, owner, name, props):
    pset = model.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(),
                               Name=name, HasProperties=[])
    pset.HasProperties = [
        model.create_entity("IfcPropertySingleValue", Name=k,
                            NominalValue=model.create_entity("IfcLabel", v))
        for k, v in props.items()
    ]
    rel = model.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(),
                              RelatedObjects=[owner], RelatingPropertyDefinition=pset)


def main():
    model = ifcopenshell.file(schema="IFC4X3_ADD2")

    def ent(type_, **kw):
        e = model.create_entity(type_, GlobalId=ifcopenshell.guid.new(), **kw)
        return e

    def point(x, y, z):
        return model.create_entity("IfcCartesianPoint", Coordinates=[x, y, z])

    def placement(x, y, z):
        loc = model.create_entity("IfcLocalPlacement",
            PlacementRelTo=None,
            RelativePlacement=model.create_entity("IfcAxis2Placement3D", Location=point(x, y, z)))
        return loc

    project = ent("IfcProject", Name="CSR independent beam-plate")
    site = ent("IfcSite", Name="Independent site")
    building = ent("IfcBuilding", Name="Independent building")
    storey = ent("IfcBuildingStorey", Name="Independent floor")
    for parent, child in [(project, site), (site, building), (building, storey)]:
        model.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(),
                            RelatingObject=parent, RelatedObjects=[child])

    # 工作区
    zone = ent("IfcSpace", Name="Independent work zone zone_a")
    model.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(),
                        RelatingObject=storey, RelatedObjects=[zone])
    pset(model, zone, "Pset_CSR_WorkZone", {"WorkZoneId": "zone_a", "Active": "True",
                                            "Payload": "payloads/zone_a.usd", "InteractionLOD": "interface"})

    # 场景
    pset(model, project, "Pset_CSR_Scene", {"SceneId": "independent_beam_plate",
                                            "RobotId": "unitree_g1",
                                            "RobotCapabilities": '["grasp","insertion"]',
                                            "UpAxis": "Z", "MetersPerUnit": "1.0"})

    # 构件: 梁 (IfcMember, 工位原点)
    beam = ent("IfcMember", Name="Independent beam", ObjectPlacement=placement(2.0, 1.5, 1.0))
    pset(model, beam, "Pset_CSR_Component", {
        "ComponentId": "independent_beam", "LengthM": "1.3", "WidthM": "0.15", "HeightM": "0.3",
        "MassKg": "12.0", "MaterialName": "S235", "WorkZoneId": "zone_a",
        "ConstructionState": "finally_connected"})

    # 构件: 连接板 (IfcPlate, 梁端, 带接口)
    plate = ent("IfcPlate", Name="Independent connection plate", ObjectPlacement=placement(2.1, 1.5, 1.0))
    pset(model, plate, "Pset_CSR_Component", {
        "ComponentId": "independent_plate", "LengthM": "0.3", "WidthM": "0.02", "HeightM": "0.24",
        "MassKg": "0.8", "MaterialName": "S235", "WorkZoneId": "zone_a",
        "ConstructionState": "finally_connected"})
    # 接口(板上的孔): 指向螺栓, 沿 -Y 轴插入
    pset(model, plate, "Pset_CSR_Interface_plate_hole", {
        "InterfaceId": "plate_hole", "InterfaceType": "insert",
        "MateComponentId": "independent_pin",
        "OriginX": "2.1", "OriginY": "1.5", "OriginZ": "1.0",
        "AxisX": "0.0", "AxisY": "-1.0", "AxisZ": "0.0", "ToleranceMm": "1.5"})

    # 构件: 螺栓/销 (IfcMechanicalFastener)
    pin = ent("IfcMechanicalFastener", Name="Independent pin", ObjectPlacement=placement(2.1, 1.4, 1.0))
    pset(model, pin, "Pset_CSR_Component", {
        "ComponentId": "independent_pin", "LengthM": "0.1", "WidthM": "0.018", "HeightM": "0.018",
        "MassKg": "0.18", "MaterialName": "S235", "WorkZoneId": "zone_a",
        "ConstructionState": "uninstalled"})

    # 任务: 把销插入板孔
    task = ent("IfcTask", Name="insert pin into plate hole")
    model.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(),
                        RelatingObject=storey, RelatedObjects=[task])
    pset(model, task, "Pset_CSR_Task", {
        "TaskId": "insert_pin_task", "TaskType": "insert", "Actor": "unitree_g1",
        "TargetComponent": "independent_plate", "InterfaceId": "plate_hole",
        "ToolId": "independent_gripper", "RequiredToolCapabilities": '["grasp","insertion"]',
        "RequiredCapabilities": '["grasp","insertion"]',
        "Preconditions": '["plate_installed"]', "SuccessCriteria": '["pin_depth_mm >= 20"]'})

    # 工具
    tool = ent("IfcConstructionEquipmentResource", Name="independent gripper")
    pset(model, tool, "Pset_CSR_Tool", {"ToolId": "independent_gripper",
                                        "AssetUri": "omniverse://g1/parallel_gripper.usd",
                                        "Capabilities": '["grasp","insertion"]'})

    model.write(str(IFC_PATH))

    # 编译 + 验证
    scene = compile_ifc(IFC_PATH)
    report = SceneValidator().validate(scene)
    out = {
        "ifc_file": IFC_PATH.name,
        "authored": "independent (hand-authored, not fixture generator)",
        "compiled": {
            "scene_id": scene["scene_id"],
            "components": len(scene["components"]),
            "interfaces": len(scene["interfaces"]),
            "workzones": len(scene["workzones"]),
            "tasks": len(scene["tasks"]),
            "provenance_records": len(scene["provenance"]),
        },
        "validation": report.to_dict(),
    }
    import json
    (OUT / "report.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
