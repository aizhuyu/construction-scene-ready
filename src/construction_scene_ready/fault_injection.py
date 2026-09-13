"""Deterministically inject known construction-scene faults."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


FAULTS = (
    "wrong_up_axis",
    "wrong_units",
    "missing_ifc_guid",
    "duplicate_ifc_guid",
    "missing_workzone_payload",
    "wrong_interaction_lod",
    "missing_robot_actor",
    "missing_target_component",
    "missing_interface",
    "missing_task_preconditions",
    "missing_success_criteria",
    "missing_robot_capability",
    "missing_interface_axis",
    "nonunit_interface_axis",
    "missing_tolerance",
    "nonpositive_tolerance",
    "missing_mate_component",
    "nonpositive_mass",
    "invalid_construction_state",
    "missing_component_workzone",
    "invalid_provenance_confidence",
    "missing_mass_provenance",
    "unsupported_generated_friction",
    "missing_tool_binding",
    "missing_tool_capability",
    "missing_interface_owner",
    "dangling_mate_component",
    "mismatched_task_interface_target",
    "unsafe_payload_path",
    "incomplete_provenance_schema",
)

COMPOUND_FAULTS = {
    "compound_frame_and_payload": ("wrong_up_axis", "missing_workzone_payload"),
    "compound_task_contract": (
        "missing_task_preconditions",
        "missing_success_criteria",
    ),
    "compound_interface_physics": (
        "nonunit_interface_axis",
        "nonpositive_tolerance",
    ),
    "compound_identity_and_actor": ("duplicate_ifc_guid", "missing_robot_actor"),
    "compound_mass_and_provenance": (
        "nonpositive_mass",
        "missing_mass_provenance",
    ),
}


EXPECTED_RULES = {
    "wrong_up_axis": ("CSR-SCN-001",),
    "wrong_units": ("CSR-SCN-002",),
    "missing_ifc_guid": ("CSR-SCN-003",),
    "duplicate_ifc_guid": ("CSR-SCN-004",),
    "missing_workzone_payload": ("CSR-SCN-005", "CSR-SCN-029"),
    "wrong_interaction_lod": ("CSR-SCN-006",),
    # A missing actor necessarily prevents capability resolution. Both the
    # root-cause rule and its deterministic consequence belong to ground truth.
    "missing_robot_actor": ("CSR-SCN-007", "CSR-SCN-011"),
    "missing_target_component": ("CSR-SCN-008", "CSR-SCN-028"),
    "missing_task_preconditions": ("CSR-SCN-009",),
    "missing_success_criteria": ("CSR-SCN-010",),
    "missing_robot_capability": ("CSR-SCN-011",),
    "missing_interface": ("CSR-SCN-012",),
    "missing_interface_axis": ("CSR-SCN-013",),
    "missing_tolerance": ("CSR-SCN-014",),
    "missing_mass_provenance": ("CSR-SCN-015",),
    "invalid_provenance_confidence": ("CSR-SCN-016",),
    "nonpositive_mass": ("CSR-SCN-017",),
    "nonunit_interface_axis": ("CSR-SCN-018",),
    "nonpositive_tolerance": ("CSR-SCN-019",),
    "missing_mate_component": ("CSR-SCN-020", "CSR-SCN-027"),
    "invalid_construction_state": ("CSR-SCN-021",),
    "missing_component_workzone": ("CSR-SCN-022",),
    "unsupported_generated_friction": ("CSR-SCN-023",),
    "missing_tool_binding": ("CSR-SCN-024",),
    "missing_tool_capability": ("CSR-SCN-025",),
    "missing_interface_owner": ("CSR-SCN-026", "CSR-SCN-028"),
    "dangling_mate_component": ("CSR-SCN-027",),
    "mismatched_task_interface_target": ("CSR-SCN-028",),
    "unsafe_payload_path": ("CSR-SCN-029",),
    "incomplete_provenance_schema": ("CSR-SCN-030",),
}


def _apply_fault(candidate: dict[str, Any], fault: str) -> None:
    if fault == "wrong_up_axis":
        candidate["coordinate_system"]["up_axis"] = "Y"
    elif fault == "wrong_units":
        candidate["coordinate_system"]["meters_per_unit"] = 0.001
    elif fault == "missing_ifc_guid":
        candidate["components"][0]["ifc_guid"] = ""
    elif fault == "duplicate_ifc_guid":
        candidate["components"][1]["ifc_guid"] = candidate["components"][0][
            "ifc_guid"
        ]
    elif fault == "missing_workzone_payload":
        candidate["workzones"][0]["payload"] = ""
    elif fault == "wrong_interaction_lod":
        candidate["workzones"][0]["interaction_lod"] = "coarse"
    elif fault == "missing_robot_actor":
        candidate["tasks"][0]["actor"] = "missing_robot"
    elif fault == "missing_target_component":
        candidate["tasks"][0]["target_component"] = "missing_component"
    elif fault == "missing_interface":
        candidate["tasks"][0]["interface"] = "missing_interface"
    elif fault == "missing_task_preconditions":
        candidate["tasks"][0]["preconditions"] = []
    elif fault == "missing_success_criteria":
        candidate["tasks"][0]["success_criteria"] = []
    elif fault == "missing_robot_capability":
        candidate["robots"][0]["capabilities"] = []
    elif fault == "missing_interface_axis":
        candidate["interfaces"][0]["axis"] = []
    elif fault == "nonunit_interface_axis":
        candidate["interfaces"][0]["axis"] = [0.0, 0.0, 2.0]
    elif fault == "missing_tolerance":
        candidate["interfaces"][0]["tolerance_mm"] = None
    elif fault == "nonpositive_tolerance":
        candidate["interfaces"][0]["tolerance_mm"] = -1.0
    elif fault == "missing_mate_component":
        candidate["interfaces"][0]["mate_component"] = ""
    elif fault == "nonpositive_mass":
        candidate["components"][0]["mass_kg"] = 0.0
    elif fault == "invalid_construction_state":
        candidate["components"][0]["construction_state"] = "almost_done"
    elif fault == "missing_component_workzone":
        candidate["components"][0]["workzone_id"] = "missing_zone"
    elif fault == "invalid_provenance_confidence":
        candidate["provenance"][0]["confidence"] = 1.5
    elif fault == "missing_mass_provenance":
        candidate["provenance"] = [
            record
            for record in candidate["provenance"]
            if record.get("property") != "mass_kg"
        ]
    elif fault == "unsupported_generated_friction":
        for record in candidate["provenance"]:
            if record.get("property") == "friction":
                record["source_type"] = "unverified_model_generation"
                record["confidence"] = 0.2
    elif fault == "missing_tool_binding":
        candidate["tasks"][0]["tool"] = ""
    elif fault == "missing_tool_capability":
        candidate["tools"][0]["capabilities"] = []
    elif fault == "missing_interface_owner":
        candidate["interfaces"][0]["component"] = "missing_component"
    elif fault == "dangling_mate_component":
        candidate["interfaces"][0]["mate_component"] = "missing_component"
    elif fault == "mismatched_task_interface_target":
        interface = candidate["interfaces"][0]
        candidate["tasks"][0]["target_component"] = interface["mate_component"]
    elif fault == "unsafe_payload_path":
        candidate["workzones"][0]["payload"] = "../../unsafe.usda"
    elif fault == "incomplete_provenance_schema":
        candidate["provenance"][0].pop("uncertainty_interval", None)
    else:
        raise ValueError(f"Unknown fault: {fault}")


def inject_fault(scene: dict[str, Any], fault: str) -> dict[str, Any]:
    candidate = copy.deepcopy(scene)
    faults = COMPOUND_FAULTS.get(fault, (fault,))
    expected_rules: list[str] = []
    for member in faults:
        _apply_fault(candidate, member)
        expected_rules.extend(EXPECTED_RULES[member])
    candidate["fault_ground_truth"] = {
        "fault": fault,
        "members": list(faults),
        "expected_rules": sorted(set(expected_rules)),
        "source_scene_id": scene["scene_id"],
    }
    candidate["scene_id"] = f"{scene['scene_id']}__{fault}"
    return candidate


def generate_fault_set(scene: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        inject_fault(scene, fault)
        for fault in (*FAULTS, *COMPOUND_FAULTS)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.scene.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for candidate in generate_fault_set(source):
        output = args.output_dir / f"{candidate['scene_id']}.json"
        output.write_text(
            json.dumps(candidate, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
