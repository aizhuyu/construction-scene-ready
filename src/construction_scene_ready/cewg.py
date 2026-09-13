"""Build a canonical Construction Embodied World Graph (CEWG)."""

from __future__ import annotations

from typing import Any


STATE_TRANSITIONS: tuple[tuple[str, str], ...] = (
    ("uninstalled", "being_transported"),
    ("being_transported", "pre_positioned"),
    ("pre_positioned", "aligned"),
    ("aligned", "partially_inserted"),
    ("partially_inserted", "temporarily_fixed"),
    ("temporarily_fixed", "finally_connected"),
    ("being_transported", "failed"),
    ("pre_positioned", "failed"),
    ("aligned", "jammed"),
    ("partially_inserted", "jammed"),
)


def _node(node_id: str, node_type: str, **attributes: Any) -> dict[str, Any]:
    return {"id": node_id, "type": node_type, "attributes": attributes}


def _edge(
    edge_type: str,
    source: str,
    target: str,
    **attributes: Any,
) -> dict[str, Any]:
    return {
        "type": edge_type,
        "source": source,
        "target": target,
        "attributes": attributes,
    }


def build_cewg(scene: dict[str, Any]) -> dict[str, Any]:
    """Convert the compiled scene IR into a stable typed property graph.

    The graph is intentionally simulator-neutral.  It makes cross-entity
    relations explicit before those relations are compiled into OpenUSD
    references, payloads, and custom attributes.
    """

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for component in scene.get("components", []):
        component_node = f"component:{component['id']}"
        nodes.append(
            _node(
                component_node,
                "BuildingComponent",
                ifc_guid=component["ifc_guid"],
                ifc_class=component.get("ifc_class"),
                name=component.get("name"),
                dimensions_m=component.get("dimensions_m"),
                position_m=component.get("position_m"),
                mass_kg=component["mass_kg"],
                material=component.get("material"),
                construction_state=component["construction_state"],
            )
        )
        edges.append(
            _edge(
                "located_in",
                component_node,
                f"workzone:{component['workzone_id']}",
            )
        )
        edges.append(
            _edge(
                "has_state",
                component_node,
                f"state:{component['construction_state']}",
            )
        )

    for interface in scene.get("interfaces", []):
        interface_node = f"interface:{interface['id']}"
        nodes.append(
            _node(
                interface_node,
                "AssemblyInterface",
                interface_type=interface.get("type"),
                origin_m=interface.get("origin_m"),
                axis=interface["axis"],
                tolerance_mm=interface["tolerance_mm"],
            )
        )
        edges.extend(
            (
                _edge(
                    "has_interface",
                    f"component:{interface['component']}",
                    interface_node,
                ),
                _edge(
                    "mates_with",
                    interface_node,
                    f"component:{interface['mate_component']}",
                ),
            )
        )

    for robot in scene.get("robots", []):
        robot_node = f"robot:{robot['id']}"
        nodes.append(
            _node(
                robot_node,
                "Robot",
                asset_uri=robot.get("asset_uri"),
                capabilities=robot.get("capabilities", []),
            )
        )
        for capability in robot.get("capabilities", []):
            capability_node = f"capability:{capability}"
            nodes.append(_node(capability_node, "RobotCapability", name=capability))
            edges.append(_edge("has_capability", robot_node, capability_node))

    for tool in scene.get("tools", []):
        tool_node = f"tool:{tool['id']}"
        nodes.append(
            _node(
                tool_node,
                "Tool",
                asset_uri=tool.get("asset_uri"),
                capabilities=tool.get("capabilities", []),
            )
        )
        for capability in tool.get("capabilities", []):
            capability_node = f"capability:{capability}"
            nodes.append(_node(capability_node, "RobotCapability", name=capability))
            edges.append(_edge("provides_capability", tool_node, capability_node))

    for zone in scene.get("workzones", []):
        nodes.append(
            _node(
                f"workzone:{zone['id']}",
                "WorkZone",
                active=zone["active"],
                payload=zone["payload"],
                interaction_lod=zone["interaction_lod"],
            )
        )

    for task in scene.get("tasks", []):
        task_node = f"task:{task['id']}"
        nodes.append(
            _node(
                task_node,
                "ConstructionTask",
                task_type=task["type"],
                preconditions=task.get("preconditions", []),
                success_criteria=task.get("success_criteria", []),
                required_tool_capabilities=task.get(
                    "required_tool_capabilities", []
                ),
            )
        )
        edges.extend(
            (
                _edge("performed_by", task_node, f"robot:{task['actor']}"),
                _edge(
                    "targets",
                    task_node,
                    f"component:{task['target_component']}",
                ),
                _edge(
                    "uses_interface",
                    task_node,
                    f"interface:{task['interface']}",
                ),
            )
        )
        if task.get("tool"):
            edges.append(
                _edge("uses_tool", task_node, f"tool:{task['tool']}")
            )
        for capability in task.get("required_capabilities", []):
            capability_node = f"capability:{capability}"
            nodes.append(_node(capability_node, "RobotCapability", name=capability))
            edges.append(_edge("requires_capability", task_node, capability_node))

    used_states = {
        component.get("construction_state", "uninstalled")
        for component in scene.get("components", [])
    }
    transition_states = {state for pair in STATE_TRANSITIONS for state in pair}
    for state in sorted(used_states | transition_states):
        nodes.append(_node(f"state:{state}", "ConstructionState", name=state))
    for source, target in STATE_TRANSITIONS:
        edges.append(
            _edge(
                "can_transition_to",
                f"state:{source}",
                f"state:{target}",
            )
        )

    for index, record in enumerate(scene.get("provenance", [])):
        provenance_id = (
            f"provenance:{record.get('entity', 'unknown')}:"
            f"{record.get('property', 'unknown')}:{index:03d}"
        )
        nodes.append(
            _node(
                provenance_id,
                "ProvenanceRecord",
                entity=record.get("entity"),
                property=record.get("property"),
                source=record.get("source"),
                source_type=record.get("source_type"),
                confidence=record.get("confidence"),
            )
        )
        entity = str(record.get("entity", ""))
        target = next(
            (
                prefix + entity
                for prefix in ("component:", "interface:", "task:")
                if any(
                    node["id"] == prefix + entity
                    for node in nodes
                )
            ),
            None,
        )
        if target:
            edges.append(
                _edge(
                    "supports_property",
                    provenance_id,
                    target,
                    property=record.get("property"),
                )
            )

    unique_nodes = {item["id"]: item for item in nodes}
    canonical_nodes = [
        unique_nodes[node_id] for node_id in sorted(unique_nodes)
    ]
    canonical_edges = sorted(
        edges,
        key=lambda item: (
            item["type"],
            item["source"],
            item["target"],
            str(item["attributes"]),
        ),
    )
    return {
        "$schema": "../schemas/cewg.schema.json",
        "schema_version": "0.1.0",
        "scene_id": scene["scene_id"],
        "source_ifc": scene.get("source_ifc"),
        "nodes": canonical_nodes,
        "edges": canonical_edges,
    }


def check_graph_integrity(graph: dict[str, Any]) -> list[str]:
    """Return graph-integrity diagnostics without external dependencies."""

    errors: list[str] = []
    node_ids = [node.get("id") for node in graph.get("nodes", [])]
    if len(node_ids) != len(set(node_ids)):
        errors.append("CEWG node identifiers shall be unique.")
    known = set(node_ids)
    for index, edge in enumerate(graph.get("edges", [])):
        if edge.get("source") not in known:
            errors.append(f"Edge {index} has unknown source {edge.get('source')!r}.")
        if edge.get("target") not in known:
            errors.append(f"Edge {index} has unknown target {edge.get('target')!r}.")
    return errors
