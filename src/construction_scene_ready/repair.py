"""Validator-grounded repair with a strict rule-to-tool whitelist.

The policy in this CPU milestone is deterministic.  A language-model policy can
later select among the same tools, but it cannot bypass their preconditions,
mutation scope, provenance log, or final validator decision.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from typing import Any, Callable

from .models import ValidationIssue
from .validator import SceneValidator

Scene = dict[str, Any]
RepairFunction = Callable[[Scene, Scene, ValidationIssue], list[str]]


@dataclass(frozen=True)
class RepairEvent:
    rule_id: str
    tool: str
    changed_paths: tuple[str, ...]
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _restore_up_axis(candidate: Scene, reference: Scene, _: ValidationIssue) -> list[str]:
    candidate["coordinate_system"]["up_axis"] = reference["coordinate_system"][
        "up_axis"
    ]
    return ["$.coordinate_system.up_axis"]


def _restore_units(candidate: Scene, reference: Scene, _: ValidationIssue) -> list[str]:
    candidate["coordinate_system"]["meters_per_unit"] = reference[
        "coordinate_system"
    ]["meters_per_unit"]
    return ["$.coordinate_system.meters_per_unit"]


def _restore_component_field(
    field: str,
) -> RepairFunction:
    def restore(candidate: Scene, reference: Scene, issue: ValidationIssue) -> list[str]:
        index = int(issue.path.split("[", 1)[1].split("]", 1)[0])
        candidate["components"][index][field] = copy.deepcopy(
            reference["components"][index][field]
        )
        return [issue.path]

    return restore


def _restore_all_component_guids(
    candidate: Scene, reference: Scene, issue: ValidationIssue
) -> list[str]:
    for index, component in enumerate(candidate["components"]):
        component["ifc_guid"] = reference["components"][index]["ifc_guid"]
    return [issue.path]


def _restore_workzone_payload(
    candidate: Scene, reference: Scene, issue: ValidationIssue
) -> list[str]:
    index = int(issue.path.split("[", 1)[1].split("]", 1)[0])
    candidate["workzones"][index]["payload"] = reference["workzones"][index][
        "payload"
    ]
    return [issue.path]


def _restore_workzone_lod(
    candidate: Scene, reference: Scene, issue: ValidationIssue
) -> list[str]:
    index = int(issue.path.split("[", 1)[1].split("]", 1)[0])
    candidate["workzones"][index]["interaction_lod"] = reference["workzones"][
        index
    ]["interaction_lod"]
    return [issue.path]


def _restore_task_field(field: str) -> RepairFunction:
    def restore(candidate: Scene, reference: Scene, issue: ValidationIssue) -> list[str]:
        index = int(issue.path.split("[", 1)[1].split("]", 1)[0])
        candidate["tasks"][index][field] = copy.deepcopy(
            reference["tasks"][index][field]
        )
        return [issue.path]

    return restore


def _restore_robot_capabilities(
    candidate: Scene, reference: Scene, issue: ValidationIssue
) -> list[str]:
    task_index = int(issue.path.split("[", 1)[1].split("]", 1)[0])
    robot_id = reference["tasks"][task_index]["actor"]
    candidate_robot = next(robot for robot in candidate["robots"] if robot["id"] == robot_id)
    reference_robot = next(robot for robot in reference["robots"] if robot["id"] == robot_id)
    candidate_robot["capabilities"] = copy.deepcopy(reference_robot["capabilities"])
    return [f"$.robots[{robot_id}].capabilities"]


def _restore_tool_capabilities(
    candidate: Scene, reference: Scene, issue: ValidationIssue
) -> list[str]:
    task_index = int(issue.path.split("[", 1)[1].split("]", 1)[0])
    tool_id = reference["tasks"][task_index]["tool"]
    candidate_tool = next(
        tool for tool in candidate["tools"] if tool["id"] == tool_id
    )
    reference_tool = next(
        tool for tool in reference["tools"] if tool["id"] == tool_id
    )
    candidate_tool["capabilities"] = copy.deepcopy(
        reference_tool["capabilities"]
    )
    return [f"$.tools[{tool_id}].capabilities"]


def _restore_interface_field(field: str) -> RepairFunction:
    def restore(candidate: Scene, reference: Scene, issue: ValidationIssue) -> list[str]:
        path_token = issue.path.split("[", 1)[1].split("]", 1)[0]
        if path_token.isdigit():
            index = int(path_token)
        else:
            index = next(
                i
                for i, interface in enumerate(candidate["interfaces"])
                if interface.get("id") == path_token
            )
        candidate["interfaces"][index][field] = copy.deepcopy(
            reference["interfaces"][index][field]
        )
        return [issue.path]

    return restore


def _restore_provenance_record(
    candidate: Scene, reference: Scene, issue: ValidationIssue
) -> list[str]:
    index = int(issue.path.split("[", 1)[1].split("]", 1)[0])
    candidate["provenance"][index] = copy.deepcopy(reference["provenance"][index])
    return [issue.path]


def _restore_task_preconditions(
    candidate: Scene, reference: Scene, issue: ValidationIssue
) -> list[str]:
    index = int(issue.path.split("[", 1)[1].split("]", 1)[0])
    candidate["tasks"][index]["preconditions"] = copy.deepcopy(
        reference["tasks"][index]["preconditions"]
    )
    return [issue.path]


def _restore_task_interface(
    candidate: Scene, reference: Scene, issue: ValidationIssue
) -> list[str]:
    index = int(issue.path.split("[", 1)[1].split("]", 1)[0])
    candidate["tasks"][index]["interface"] = reference["tasks"][index]["interface"]
    return [issue.path]


def _restore_mass_provenance(
    candidate: Scene, reference: Scene, _: ValidationIssue
) -> list[str]:
    restored = [
        copy.deepcopy(record)
        for record in reference["provenance"]
        if record.get("property") == "mass_kg"
    ]
    candidate["provenance"].extend(restored)
    return ["$.provenance"]


WHITELIST: dict[str, tuple[str, RepairFunction]] = {
    "CSR-SCN-001": ("restore_coordinate_frame", _restore_up_axis),
    "CSR-SCN-002": ("restore_scene_units", _restore_units),
    "CSR-SCN-003": ("restore_ifc_guid", _restore_component_field("ifc_guid")),
    "CSR-SCN-004": ("restore_unique_ifc_guids", _restore_all_component_guids),
    "CSR-SCN-005": ("restore_task_payload", _restore_workzone_payload),
    "CSR-SCN-006": ("restore_interaction_lod", _restore_workzone_lod),
    "CSR-SCN-007": ("restore_task_actor", _restore_task_field("actor")),
    "CSR-SCN-008": (
        "restore_target_component",
        _restore_task_field("target_component"),
    ),
    "CSR-SCN-009": ("restore_state_preconditions", _restore_task_preconditions),
    "CSR-SCN-010": (
        "restore_success_criteria",
        _restore_task_field("success_criteria"),
    ),
    "CSR-SCN-011": ("restore_robot_capabilities", _restore_robot_capabilities),
    "CSR-SCN-012": ("restore_interface_binding", _restore_task_interface),
    "CSR-SCN-013": ("restore_interface_axis", _restore_interface_field("axis")),
    "CSR-SCN-014": (
        "restore_interface_tolerance",
        _restore_interface_field("tolerance_mm"),
    ),
    "CSR-SCN-015": ("restore_mass_provenance", _restore_mass_provenance),
    "CSR-SCN-016": ("restore_provenance_record", _restore_provenance_record),
    "CSR-SCN-017": ("restore_component_mass", _restore_component_field("mass_kg")),
    "CSR-SCN-018": (
        "normalize_interface_axis",
        _restore_interface_field("axis"),
    ),
    "CSR-SCN-019": (
        "restore_positive_tolerance",
        _restore_interface_field("tolerance_mm"),
    ),
    "CSR-SCN-020": (
        "restore_mating_component",
        _restore_interface_field("mate_component"),
    ),
    "CSR-SCN-021": (
        "restore_construction_state",
        _restore_component_field("construction_state"),
    ),
    "CSR-SCN-022": (
        "restore_component_workzone",
        _restore_component_field("workzone_id"),
    ),
    "CSR-SCN-024": ("restore_task_tool", _restore_task_field("tool")),
    "CSR-SCN-025": (
        "restore_tool_capabilities",
        _restore_tool_capabilities,
    ),
    "CSR-SCN-026": (
        "restore_interface_owner",
        _restore_interface_field("component"),
    ),
    "CSR-SCN-027": (
        "restore_mating_component_reference",
        _restore_interface_field("mate_component"),
    ),
    "CSR-SCN-028": (
        "restore_interface_target_binding",
        _restore_task_field("target_component"),
    ),
    "CSR-SCN-029": (
        "restore_safe_payload_path",
        _restore_workzone_payload,
    ),
    "CSR-SCN-030": (
        "restore_provenance_contract",
        _restore_provenance_record,
    ),
}


def repair_scene(
    faulty_scene: Scene,
    evidence_scene: Scene,
    *,
    validator: SceneValidator | None = None,
) -> tuple[Scene, dict[str, Any]]:
    """Repair only validator findings covered by the whitelist.

    ``evidence_scene`` represents trusted compiler/ground-truth evidence in this
    milestone.  Future tools may retrieve the same fields from IFC or an
    approved engineering database.
    """

    validator = validator or SceneValidator()
    candidate = copy.deepcopy(faulty_scene)
    before = validator.validate(candidate)
    events: list[RepairEvent] = []
    blocked: list[str] = []

    for issue in before.issues:
        tool_entry = WHITELIST.get(issue.rule_id)
        if tool_entry is None:
            blocked.append(issue.rule_id)
            continue
        tool_name, function = tool_entry
        changed_paths = function(candidate, evidence_scene, issue)
        events.append(
            RepairEvent(
                rule_id=issue.rule_id,
                tool=tool_name,
                changed_paths=tuple(changed_paths),
                evidence=f"trusted-scene:{evidence_scene['scene_id']}",
            )
        )

    after = validator.validate(candidate)
    audit = {
        "source_scene_id": faulty_scene["scene_id"],
        "evidence_scene_id": evidence_scene["scene_id"],
        "before": before.to_dict(),
        "events": [event.to_dict() for event in events],
        "blocked_rule_ids": sorted(set(blocked)),
        "after": after.to_dict(),
        "accepted": after.passed and not blocked,
    }
    return candidate, audit
