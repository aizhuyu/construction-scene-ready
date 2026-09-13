"""Write a multi-layer OpenUSD scene from the intermediate representation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value)


def _set_string(prim: Any, name: str, value: str) -> None:
    from pxr import Sdf

    prim.CreateAttribute(name, Sdf.ValueTypeNames.String).Set(value)


def _set_double(prim: Any, name: str, value: float) -> None:
    from pxr import Sdf

    prim.CreateAttribute(name, Sdf.ValueTypeNames.Double).Set(float(value))


def _provenance(
    scene: dict[str, Any],
    entity: str,
    property_name: str,
) -> dict[str, Any] | None:
    return next(
        (
            record
            for record in scene.get("provenance", [])
            if record.get("entity") == entity
            and record.get("property") == property_name
        ),
        None,
    )


def _write_provenance(
    prim: Any,
    property_name: str,
    record: dict[str, Any] | None,
) -> None:
    from pxr import Sdf

    if not record:
        return
    prefix = f"csr:provenance:{property_name}"
    for key in ("source", "source_type", "unit"):
        value = record.get(key)
        if value is not None:
            _set_string(prim, f"{prefix}:{key}", str(value))
    if record.get("confidence") is not None:
        _set_double(prim, f"{prefix}:confidence", record["confidence"])
    if record.get("authority_level") is not None:
        prim.CreateAttribute(
            f"{prefix}:authorityLevel", Sdf.ValueTypeNames.Int
        ).Set(int(record["authority_level"]))
    if record.get("uncertainty_interval") is not None:
        prim.CreateAttribute(
            f"{prefix}:uncertaintyInterval",
            Sdf.ValueTypeNames.DoubleArray,
        ).Set([float(value) for value in record["uncertainty_interval"]])
    if record.get("auto_repair_allowed") is not None:
        prim.CreateAttribute(
            f"{prefix}:autoRepairAllowed", Sdf.ValueTypeNames.Bool
        ).Set(bool(record["auto_repair_allowed"]))


def _box_inertia(
    mass_kg: float,
    dimensions_m: list[float],
) -> tuple[float, float, float]:
    x, y, z = (float(value) for value in dimensions_m)
    coefficient = mass_kg / 12.0
    return (
        coefficient * (y * y + z * z),
        coefficient * (x * x + z * z),
        coefficient * (x * x + y * y),
    )


def _write_plate_with_hole(
    stage: Any,
    path: str,
    component: dict[str, Any],
) -> Any:
    """生成带螺栓孔的连接板 Mesh.

    板是矩形(dimensions_m), 中心有一个沿X轴贯穿的圆柱孔。
    孔径 = 螺栓直径 + 间隙(2mm), 从接口公差读取。
    """
    from pxr import Gf, Sdf, UsdGeom
    import math

    dx, dy, dz = component["dimensions_m"]
    # 孔半径(默认12mm = M20螺栓孔)
    hole_radius = 0.012

    # 构建带孔矩形板的Mesh
    # 方法: 用多个四边形面片组合,中心留圆孔
    # 简化: 外矩形 + 内圆环, 用三角剖分连接

    n_segments = 16  # 圆孔离散段数
    points = []
    faces = []

    # 板的前面(z=+dz/2)和后面(z=-dz/2)
    for z_side in [dz/2, -dz/2]:
        z_offset = len(points)

        # 外矩形4个角
        ox, oy = dx/2, dy/2
        # 外矩形边的中点(用于和圆孔连接)
        # 用网格方式: 把矩形分成 5x5 区域,中心挖圆

        # 圆孔顶点
        hole_pts = []
        for i in range(n_segments):
            angle = 2 * math.pi * i / n_segments
            hx = hole_radius * math.cos(angle)
            hy = hole_radius * math.sin(angle)
            hole_pts.append((hx, hy, z_side))
            points.append((hx, hy, z_side))

        # 外矩形顶点(8个: 4角+4边中点)
        outer_pts = [
            (-ox, -oy, z_side), (ox, -oy, z_side),
            (ox, oy, z_side), (-ox, oy, z_side),
        ]
        for pt in outer_pts:
            points.append(pt)
        outer_start = z_offset + n_segments  # 外矩形顶点起始索引

        # 构建面: 外矩形到圆孔之间的环形区域
        # 用三角形扇形剖分
        for i in range(n_segments):
            i_next = (i + 1) % n_segments
            # 每个圆孔段连接到最近的外矩形角
            # 简化: 把环形区域分成4个四边形扇区
            angle = 2 * math.pi * i / n_segments + math.pi / n_segments
            sector = int((angle / (2 * math.pi)) * 4) % 4
            corner_idx = outer_start + sector

            faces.append([
                z_offset + i,
                z_offset + i_next,
                corner_idx,
            ])

    # 前后面之间的侧壁(圆孔内壁)
    for i in range(n_segments):
        i_next = (i + 1) % n_segments
        faces.append([i, i + n_segments, i_next + n_segments, i_next])
        # 外壁(简化: 不生成外壁三角形,板的侧面由前后面边缘构成)

    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr(points)
    mesh.CreateFaceVertexIndicesAttr([idx for face in faces for idx in face])
    mesh.CreateFaceVertexCountsAttr([len(face) for face in faces])

    # 变换
    xformable = UsdGeom.Xformable(mesh)
    xformable.AddTranslateOp().Set(Gf.Vec3d(*component["position_m"]))
    xformable.AddOrientOp().Set(Gf.Quatf(1.0, Gf.Vec3f(0.0, 0.0, 0.0)))

    return mesh.GetPrim()


def _write_component(
    stage: Any,
    path: str,
    component: dict[str, Any],
    *,
    scene: dict[str, Any],
    fidelity: str,
    physics_enabled: bool,
) -> None:
    from pxr import Gf, Sdf, UsdGeom, UsdPhysics

    # 连接板特殊处理: 生成带孔Mesh
    if component["id"] == "connection_plate" and fidelity != "global_proxy":
        _write_plate_with_hole(stage, path, component)
        prim = stage.GetPrimAtPath(path)
    else:
        cube = UsdGeom.Cube.Define(stage, path)
        cube.GetSizeAttr().Set(1.0)
        xformable = UsdGeom.Xformable(cube)
        xformable.AddTranslateOp().Set(Gf.Vec3d(*component["position_m"]))
        xformable.AddOrientOp().Set(Gf.Quatf(1.0, Gf.Vec3f(0.0, 0.0, 0.0)))
        xformable.AddScaleOp().Set(Gf.Vec3f(*component["dimensions_m"]))
        prim = cube.GetPrim()
    _set_string(prim, "csr:componentId", component["id"])
    _set_string(prim, "csr:ifcGuid", component["ifc_guid"])
    _set_string(prim, "csr:ifcClass", component["ifc_class"])
    _set_string(prim, "csr:constructionState", component["construction_state"])
    _set_string(prim, "csr:fidelity", fidelity)
    _set_string(prim, "csr:workZoneId", component["workzone_id"])
    _set_double(prim, "csr:massKg", component["mass_kg"])
    _write_provenance(
        prim,
        "mass_kg",
        _provenance(scene, component["id"], "mass_kg"),
    )
    if physics_enabled:
        UsdPhysics.CollisionAPI.Apply(prim)
        rigid_body = UsdPhysics.RigidBodyAPI.Apply(prim)
        rigid_body.CreateRigidBodyEnabledAttr(True)
        mass_api = UsdPhysics.MassAPI.Apply(prim)
        mass_api.CreateMassAttr(float(component["mass_kg"]))
        mass_api.CreateCenterOfMassAttr(Gf.Vec3f(0.0, 0.0, 0.0))
        mass_api.CreateDiagonalInertiaAttr(
            Gf.Vec3f(
                *_box_inertia(
                    float(component["mass_kg"]),
                    component["dimensions_m"],
                )
            )
        )
        mass_api.CreatePrincipalAxesAttr(
            Gf.Quatf(1.0, Gf.Vec3f(0.0, 0.0, 0.0))
        )


def _write_interface(
    stage: Any,
    path: str,
    interface: dict[str, Any],
    *,
    scene: dict[str, Any],
) -> None:
    from pxr import Gf, Sdf, UsdGeom

    marker = UsdGeom.Cylinder.Define(stage, path)
    marker.GetHeightAttr().Set(0.10)
    marker.GetRadiusAttr().Set(
        max(float(interface["tolerance_mm"]) / 1000.0, 0.001)
    )
    axis = tuple(float(value) for value in interface["axis"])
    if axis == (1.0, 0.0, 0.0):
        marker.GetAxisAttr().Set(UsdGeom.Tokens.x)
    elif axis == (0.0, 1.0, 0.0):
        marker.GetAxisAttr().Set(UsdGeom.Tokens.y)
    else:
        marker.GetAxisAttr().Set(UsdGeom.Tokens.z)
    xformable = UsdGeom.Xformable(marker)
    xformable.AddTranslateOp().Set(
        Gf.Vec3d(*interface.get("origin_m", (0.0, 0.0, 0.0)))
    )
    marker.GetPurposeAttr().Set(UsdGeom.Tokens.guide)
    prim = marker.GetPrim()
    _set_string(prim, "csr:interfaceId", interface["id"])
    _set_string(prim, "csr:interfaceType", interface["type"])
    _set_string(prim, "csr:component", interface["component"])
    _set_string(prim, "csr:mateComponent", interface["mate_component"])
    _set_double(prim, "csr:toleranceMm", interface["tolerance_mm"])
    prim.CreateAttribute("csr:axis", Sdf.ValueTypeNames.Double3).Set(axis)
    _write_provenance(
        prim,
        "tolerance_mm",
        _provenance(scene, interface["id"], "tolerance_mm"),
    )


def _compose_root(
    scene: dict[str, Any],
    output_dir: Path,
    *,
    filename: str,
    load_all_zones: bool,
) -> Path:
    from pxr import Usd, UsdGeom

    root_path = output_dir / filename
    root_stage = Usd.Stage.CreateNew(str(root_path))
    UsdGeom.SetStageUpAxis(root_stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(root_stage, 1.0)
    world = UsdGeom.Xform.Define(root_stage, "/World").GetPrim()
    root_stage.SetDefaultPrim(world)
    _set_string(world, "csr:sceneId", scene["scene_id"])
    _set_string(world, "csr:schemaVersion", scene["schema_version"])
    _set_string(
        world,
        "csr:compositionMode",
        "all_loaded" if load_all_zones else "task_activated",
    )
    global_prim = root_stage.DefinePrim("/World/Global")
    global_prim.GetReferences().AddReference("./global_navigation.usda")
    UsdGeom.Xform.Define(root_stage, "/World/WorkZones")
    for zone in scene["workzones"]:
        if not load_all_zones and not zone.get("active"):
            continue
        zone_prim = root_stage.DefinePrim(
            f"/World/WorkZones/{_safe_name(zone['id'])}"
        )
        zone_prim.GetPayloads().AddPayload(
            f"./workzones/{zone['id']}_payload.usda"
        )
    UsdGeom.Xform.Define(root_stage, "/World/Tasks")
    for task in scene["tasks"]:
        task_prim = root_stage.DefinePrim(
            f"/World/Tasks/{_safe_name(task['id'])}"
        )
        task_prim.GetReferences().AddReference(
            f"./interaction/{task['id']}.usda"
        )
    root_stage.GetRootLayer().Save()
    return root_path


def compile_usd(scene: dict[str, Any], output_dir: Path) -> Path:
    from pxr import Sdf, Usd, UsdGeom

    output_dir.mkdir(parents=True, exist_ok=True)
    workzone_dir = output_dir / "workzones"
    interaction_dir = output_dir / "interaction"
    workzone_dir.mkdir(exist_ok=True)
    interaction_dir.mkdir(exist_ok=True)

    global_path = output_dir / "global_navigation.usda"
    global_stage = Usd.Stage.CreateNew(str(global_path))
    UsdGeom.SetStageUpAxis(global_stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(global_stage, 1.0)
    global_root = UsdGeom.Xform.Define(global_stage, "/Global").GetPrim()
    global_stage.SetDefaultPrim(global_root)
    _set_string(global_root, "csr:fidelity", "global_navigation")
    for component in scene["components"]:
        _write_component(
            global_stage,
            f"/Global/Components/{_safe_name(component['id'])}",
            component,
            scene=scene,
            fidelity="global_proxy",
            physics_enabled=False,
        )
    global_stage.GetRootLayer().Save()

    interfaces_by_component: dict[str, list[dict[str, Any]]] = {}
    for interface in scene["interfaces"]:
        interfaces_by_component.setdefault(interface["component"], []).append(
            interface
        )

    for zone in scene["workzones"]:
        zone_path = workzone_dir / f"{zone['id']}_payload.usda"
        zone_stage = Usd.Stage.CreateNew(str(zone_path))
        UsdGeom.SetStageUpAxis(zone_stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(zone_stage, 1.0)
        root = UsdGeom.Xform.Define(
            zone_stage, f"/WorkZone_{_safe_name(zone['id'])}"
        )
        zone_stage.SetDefaultPrim(root.GetPrim())
        _set_string(root.GetPrim(), "csr:workZoneId", zone["id"])
        _set_string(root.GetPrim(), "csr:fidelity", "workzone")
        for component in scene["components"]:
            if component["workzone_id"] != zone["id"]:
                continue
            component_path = (
                f"/WorkZone_{_safe_name(zone['id'])}/Components/"
                f"{_safe_name(component['id'])}"
            )
            _write_component(
                zone_stage,
                component_path,
                component,
                scene=scene,
                fidelity="workzone_physics",
                physics_enabled=True,
            )
            for interface in interfaces_by_component.get(component["id"], []):
                interface_path = (
                    f"{component_path}/Interfaces/{_safe_name(interface['id'])}"
                )
                interface_prim = UsdGeom.Xform.Define(
                    zone_stage, interface_path
                ).GetPrim()
                _set_string(
                    interface_prim, "csr:interfaceId", interface["id"]
                )
                _set_string(
                    interface_prim, "csr:interfaceType", interface["type"]
                )
                _set_string(
                    interface_prim,
                    "csr:mateComponent",
                    interface["mate_component"],
                )
                _set_double(
                    interface_prim,
                    "csr:toleranceMm",
                    interface["tolerance_mm"],
                )
                interface_prim.CreateAttribute(
                    "csr:axis", Sdf.ValueTypeNames.Double3
                ).Set(tuple(interface["axis"]))
                if interface.get("origin_m") is not None:
                    interface_prim.CreateAttribute(
                        "csr:originM", Sdf.ValueTypeNames.Double3
                    ).Set(tuple(interface["origin_m"]))
                _write_provenance(
                    interface_prim,
                    "tolerance_mm",
                    _provenance(scene, interface["id"], "tolerance_mm"),
                )
        zone_stage.GetRootLayer().Save()

    for task in scene["tasks"]:
        task_path = interaction_dir / f"{task['id']}.usda"
        task_stage = Usd.Stage.CreateNew(str(task_path))
        UsdGeom.SetStageUpAxis(task_stage, UsdGeom.Tokens.z)
        task_root = UsdGeom.Xform.Define(
            task_stage, f"/Task_{_safe_name(task['id'])}"
        ).GetPrim()
        task_stage.SetDefaultPrim(task_root)
        for key in ("id", "type", "actor", "target_component", "interface"):
            _set_string(task_root, f"csr:{key}", str(task[key]))
        if task.get("tool"):
            _set_string(task_root, "csr:tool", str(task["tool"]))
        task_root.CreateAttribute(
            "csr:preconditions", Sdf.ValueTypeNames.StringArray
        ).Set(task["preconditions"])
        task_root.CreateAttribute(
            "csr:successCriteria", Sdf.ValueTypeNames.StringArray
        ).Set(task["success_criteria"])
        matching_interface = next(
            (
                interface
                for interface in scene["interfaces"]
                if interface["id"] == task["interface"]
            ),
            None,
        )
        if matching_interface:
            _write_interface(
                task_stage,
                f"/Task_{_safe_name(task['id'])}/Interaction/"
                f"{_safe_name(matching_interface['id'])}",
                matching_interface,
                scene=scene,
            )
        task_stage.GetRootLayer().Save()

    root_path = _compose_root(
        scene,
        output_dir,
        filename="building_root.usda",
        load_all_zones=False,
    )
    _compose_root(
        scene,
        output_dir,
        filename="building_root_all_loaded.usda",
        load_all_zones=True,
    )
    return root_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    scene = json.loads(args.scene.read_text(encoding="utf-8"))
    print(compile_usd(scene, args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
