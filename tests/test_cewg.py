from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from construction_scene_ready.cewg import build_cewg, check_graph_integrity


def _scene() -> dict:
    return json.loads(
        Path("examples/minimal_scene.json").read_text(encoding="utf-8")
    )


def test_cewg_has_closed_cross_entity_relations() -> None:
    graph = build_cewg(_scene())

    assert check_graph_integrity(graph) == []
    node_types = {node["type"] for node in graph["nodes"]}
    edge_types = {edge["type"] for edge in graph["edges"]}
    assert {
        "BuildingComponent",
        "AssemblyInterface",
        "Robot",
        "WorkZone",
        "ConstructionTask",
        "ConstructionState",
        "ProvenanceRecord",
    } <= node_types
    assert {
        "located_in",
        "has_interface",
        "mates_with",
        "performed_by",
        "targets",
        "uses_interface",
        "can_transition_to",
    } <= edge_types


def test_cewg_is_canonical() -> None:
    first = build_cewg(_scene())
    second = build_cewg(_scene())
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_cewg_matches_published_json_schema() -> None:
    graph = build_cewg(_scene())
    schema = json.loads(
        Path("schemas/cewg.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(graph)
