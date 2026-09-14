"""Scene-level checks that intentionally go beyond single-asset validation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Any

from .models import ValidationIssue, ValidationReport

Scene = dict[str, Any]
Rule = Callable[[Scene], list[ValidationIssue]]


class SceneValidator:
    """Run a versioned set of construction scene-readiness rules."""

    #: Named rule groups, used by ablation switches (e.g. A1/A2) to disable a
    #: feature family without touching individual rules.
    RULE_GROUPS: dict[str, tuple[str, ...]] = {
        "coordinate": ("_coordinate_system",),
        "identity": ("_unique_component_identifiers",),
        "composition": (
            "_workzone_payloads",
            "_component_workzones",
            "_payload_paths",
        ),
        "task": ("_task_references", "_task_contracts", "_task_capabilities"),
        "interface": ("_interaction_interfaces", "_interface_closure"),
        "provenance": (
            "_critical_property_provenance",
            "_unsupported_property_sources",
            "_provenance_schema",
        ),
        "physics": ("_physical_sanity",),
        "state": ("_construction_state",),
        "tool": ("_tool_bindings",),
        # contract v0.3.0: rules added after the humanoid blind-spot study
        "interface_fidelity": (
            "_interface_coordinate_fidelity",
            "_interface_clearance_sufficiency",
        ),
    }

    def __init__(self, disabled_groups: tuple[str, ...] = (),
                 contract_version: str = "0.2.0") -> None:
        unknown = set(disabled_groups) - set(self.RULE_GROUPS)
        if unknown:
            raise ValueError(f"Unknown rule groups: {sorted(unknown)}")
        disabled = {
            method
            for group in disabled_groups
            for method in self.RULE_GROUPS[group]
        }
        # contract v0.2.0 (frozen benchmark): interface_fidelity group absent
        if contract_version == "0.2.0":
            disabled |= set(self.RULE_GROUPS["interface_fidelity"])
        elif contract_version != "0.3.0":
            raise ValueError(f"Unknown contract version: {contract_version}")
        self._rules: tuple[Rule, ...] = tuple(
            rule
            for name, rule in (
                ("_coordinate_system", self._coordinate_system),
                ("_unique_component_identifiers", self._unique_component_identifiers),
                ("_workzone_payloads", self._workzone_payloads),
                ("_task_references", self._task_references),
                ("_task_contracts", self._task_contracts),
                ("_task_capabilities", self._task_capabilities),
                ("_interaction_interfaces", self._interaction_interfaces),
                ("_critical_property_provenance", self._critical_property_provenance),
                ("_physical_sanity", self._physical_sanity),
                ("_construction_state", self._construction_state),
                ("_component_workzones", self._component_workzones),
                ("_unsupported_property_sources", self._unsupported_property_sources),
                ("_tool_bindings", self._tool_bindings),
                ("_interface_closure", self._interface_closure),
                ("_payload_paths", self._payload_paths),
                ("_provenance_schema", self._provenance_schema),
                ("_interface_coordinate_fidelity", self._interface_coordinate_fidelity),
                ("_interface_clearance_sufficiency", self._interface_clearance_sufficiency),
            )
            if name not in disabled
        )

    def validate(self, scene: Scene) -> ValidationReport:
        issues: list[ValidationIssue] = []
        for rule in self._rules:
            issues.extend(rule(scene))
        issues.sort(key=lambda item: (item.rule_id, item.path, item.message))
        return ValidationReport(
            scene_id=str(scene.get("scene_id", "<missing-scene-id>")),
            issues=tuple(issues),
        )

    @staticmethod
    def _issue(rule_id: str, path: str, message: str) -> ValidationIssue:
        return ValidationIssue(
            rule_id=rule_id,
            severity="critical",
            path=path,
            message=message,
        )

    def _coordinate_system(self, scene: Scene) -> list[ValidationIssue]:
        coordinate_system = scene.get("coordinate_system", {})
        issues: list[ValidationIssue] = []
        if coordinate_system.get("up_axis") != "Z":
            issues.append(
                self._issue(
                    "CSR-SCN-001",
                    "$.coordinate_system.up_axis",
                    "Construction scenes shall use a declared Z-up frame.",
                )
            )
        if coordinate_system.get("meters_per_unit") != 1.0:
            issues.append(
                self._issue(
                    "CSR-SCN-002",
                    "$.coordinate_system.meters_per_unit",
                    "Scene units shall be normalized to meters.",
                )
            )
        return issues

    def _unique_component_identifiers(self, scene: Scene) -> list[ValidationIssue]:
        components = scene.get("components", [])
        identifiers = [component.get("ifc_guid") for component in components]
        issues: list[ValidationIssue] = []
        for index, identifier in enumerate(identifiers):
            if not identifier:
                issues.append(
                    self._issue(
                        "CSR-SCN-003",
                        f"$.components[{index}].ifc_guid",
                        "Every construction component shall retain an IFC GUID.",
                    )
                )
        duplicates = {
            identifier
            for identifier, count in Counter(identifiers).items()
            if identifier and count > 1
        }
        for identifier in sorted(duplicates):
            issues.append(
                self._issue(
                    "CSR-SCN-004",
                    "$.components",
                    f"IFC GUID '{identifier}' is not unique in the scene.",
                )
            )
        return issues

    def _workzone_payloads(self, scene: Scene) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for index, zone in enumerate(scene.get("workzones", [])):
            if zone.get("active") and not zone.get("payload"):
                issues.append(
                    self._issue(
                        "CSR-SCN-005",
                        f"$.workzones[{index}].payload",
                        "An active work zone shall declare its task-loaded USD payload.",
                    )
                )
            if zone.get("active") and zone.get("interaction_lod") != "interface":
                issues.append(
                    self._issue(
                        "CSR-SCN-006",
                        f"$.workzones[{index}].interaction_lod",
                        "An active assembly zone shall load interface-level geometry.",
                    )
                )
        return issues

    def _task_references(self, scene: Scene) -> list[ValidationIssue]:
        component_ids = {
            component.get("id") for component in scene.get("components", [])
        }
        robot_ids = {robot.get("id") for robot in scene.get("robots", [])}
        issues: list[ValidationIssue] = []
        for index, task in enumerate(scene.get("tasks", [])):
            if task.get("actor") not in robot_ids:
                issues.append(
                    self._issue(
                        "CSR-SCN-007",
                        f"$.tasks[{index}].actor",
                        "Task actor shall reference a robot present in the scene.",
                    )
                )
            if task.get("target_component") not in component_ids:
                issues.append(
                    self._issue(
                        "CSR-SCN-008",
                        f"$.tasks[{index}].target_component",
                        "Task target shall reference a construction component.",
                    )
                )
        return issues

    def _task_contracts(self, scene: Scene) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for index, task in enumerate(scene.get("tasks", [])):
            if not task.get("preconditions"):
                issues.append(
                    self._issue(
                        "CSR-SCN-009",
                        f"$.tasks[{index}].preconditions",
                        "Every task shall declare construction-state preconditions.",
                    )
                )
            if not task.get("success_criteria"):
                issues.append(
                    self._issue(
                        "CSR-SCN-010",
                        f"$.tasks[{index}].success_criteria",
                        "Every task shall declare machine-checkable success criteria.",
                    )
                )
        return issues

    def _task_capabilities(self, scene: Scene) -> list[ValidationIssue]:
        robots = {robot.get("id"): robot for robot in scene.get("robots", [])}
        issues: list[ValidationIssue] = []
        for index, task in enumerate(scene.get("tasks", [])):
            robot = robots.get(task.get("actor"), {})
            available = set(robot.get("capabilities", []))
            required = set(task.get("required_capabilities", []))
            missing = sorted(required - available)
            if missing:
                issues.append(
                    self._issue(
                        "CSR-SCN-011",
                        f"$.tasks[{index}].required_capabilities",
                        f"Task requires unavailable robot capabilities: {missing}.",
                    )
                )
        return issues

    def _interaction_interfaces(self, scene: Scene) -> list[ValidationIssue]:
        interfaces = {
            interface.get("id"): interface
            for interface in scene.get("interfaces", [])
        }
        issues: list[ValidationIssue] = []
        for index, task in enumerate(scene.get("tasks", [])):
            if task.get("type") not in {"align", "insert", "fasten", "assemble"}:
                continue
            interface = interfaces.get(task.get("interface"))
            if not interface:
                issues.append(
                    self._issue(
                        "CSR-SCN-012",
                        f"$.tasks[{index}].interface",
                        "An interaction task shall reference an assembly interface.",
                    )
                )
                continue
            if not interface.get("axis"):
                issues.append(
                    self._issue(
                        "CSR-SCN-013",
                        f"$.interfaces[{task.get('interface')}].axis",
                        "Insertion/alignment interfaces shall define an axis.",
                    )
                )
            if interface.get("tolerance_mm") is None:
                issues.append(
                    self._issue(
                        "CSR-SCN-014",
                        f"$.interfaces[{task.get('interface')}].tolerance_mm",
                        "Assembly interfaces shall define a tolerance.",
                    )
                )
        return issues

    def _critical_property_provenance(self, scene: Scene) -> list[ValidationIssue]:
        critical_keys = {"mass_kg", "friction", "tolerance_mm"}
        records = scene.get("provenance", [])
        recorded = {record.get("property") for record in records}
        issues: list[ValidationIssue] = []
        for key in sorted(critical_keys - recorded):
            issues.append(
                self._issue(
                    "CSR-SCN-015",
                    "$.provenance",
                    f"Critical property '{key}' lacks a source and confidence record.",
                )
            )
        for index, record in enumerate(records):
            confidence = record.get("confidence")
            if confidence is None or not 0.0 <= confidence <= 1.0:
                issues.append(
                    self._issue(
                        "CSR-SCN-016",
                        f"$.provenance[{index}].confidence",
                        "Provenance confidence shall be a number in [0, 1].",
                    )
                )
        return issues

    def _physical_sanity(self, scene: Scene) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for index, component in enumerate(scene.get("components", [])):
            if component.get("mass_kg", 0) <= 0:
                issues.append(
                    self._issue(
                        "CSR-SCN-017",
                        f"$.components[{index}].mass_kg",
                        "A dynamic construction component shall have positive mass.",
                    )
                )
        for index, interface in enumerate(scene.get("interfaces", [])):
            axis = interface.get("axis")
            if axis:
                squared_norm = sum(float(value) ** 2 for value in axis)
                if abs(squared_norm - 1.0) > 1e-6:
                    issues.append(
                        self._issue(
                            "CSR-SCN-018",
                            f"$.interfaces[{index}].axis",
                            "An assembly-interface axis shall be a unit vector.",
                        )
                    )
            tolerance = interface.get("tolerance_mm")
            if tolerance is not None and tolerance <= 0:
                issues.append(
                    self._issue(
                        "CSR-SCN-019",
                        f"$.interfaces[{index}].tolerance_mm",
                        "An assembly tolerance shall be greater than zero.",
                    )
                )
            if not interface.get("mate_component"):
                issues.append(
                    self._issue(
                        "CSR-SCN-020",
                        f"$.interfaces[{index}].mate_component",
                        "An assembly interface shall identify its mating component.",
                    )
                )
        return issues

    def _construction_state(self, scene: Scene) -> list[ValidationIssue]:
        allowed = {
            "uninstalled",
            "being_transported",
            "pre_positioned",
            "aligned",
            "partially_inserted",
            "temporarily_fixed",
            "finally_connected",
            "failed",
            "jammed",
        }
        issues: list[ValidationIssue] = []
        for index, component in enumerate(scene.get("components", [])):
            if component.get("construction_state") not in allowed:
                issues.append(
                    self._issue(
                        "CSR-SCN-021",
                        f"$.components[{index}].construction_state",
                        "Component state is outside the construction-state vocabulary.",
                    )
                )
        return issues

    def _component_workzones(self, scene: Scene) -> list[ValidationIssue]:
        zone_ids = {zone.get("id") for zone in scene.get("workzones", [])}
        issues: list[ValidationIssue] = []
        for index, component in enumerate(scene.get("components", [])):
            if component.get("workzone_id") not in zone_ids:
                issues.append(
                    self._issue(
                        "CSR-SCN-022",
                        f"$.components[{index}].workzone_id",
                        "Every task component shall belong to a declared work zone.",
                    )
                )
        return issues

    def _unsupported_property_sources(self, scene: Scene) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for index, record in enumerate(scene.get("provenance", [])):
            if record.get("source_type") == "unverified_model_generation":
                issues.append(
                    self._issue(
                        "CSR-SCN-023",
                        f"$.provenance[{index}].source_type",
                        "A critical physical property cannot rely solely on an "
                        "unverified generated value.",
                    )
                )
        return issues

    def _tool_bindings(self, scene: Scene) -> list[ValidationIssue]:
        tools = {tool.get("id"): tool for tool in scene.get("tools", [])}
        issues: list[ValidationIssue] = []
        for index, task in enumerate(scene.get("tasks", [])):
            tool_id = task.get("tool")
            tool = tools.get(tool_id)
            if not tool_id or not tool:
                issues.append(
                    self._issue(
                        "CSR-SCN-024",
                        f"$.tasks[{index}].tool",
                        "An assembly task shall reference a tool present in the scene.",
                    )
                )
                continue
            available = set(tool.get("capabilities", []))
            required = set(task.get("required_tool_capabilities", []))
            missing = sorted(required - available)
            if missing:
                issues.append(
                    self._issue(
                        "CSR-SCN-025",
                        f"$.tasks[{index}].required_tool_capabilities",
                        f"Task requires unavailable tool capabilities: {missing}.",
                    )
                )
        return issues

    def _interface_closure(self, scene: Scene) -> list[ValidationIssue]:
        component_ids = {
            component.get("id") for component in scene.get("components", [])
        }
        interfaces = {
            interface.get("id"): interface
            for interface in scene.get("interfaces", [])
        }
        issues: list[ValidationIssue] = []
        for index, interface in enumerate(scene.get("interfaces", [])):
            if interface.get("component") not in component_ids:
                issues.append(
                    self._issue(
                        "CSR-SCN-026",
                        f"$.interfaces[{index}].component",
                        "An interface owner shall reference a scene component.",
                    )
                )
            if interface.get("mate_component") not in component_ids:
                issues.append(
                    self._issue(
                        "CSR-SCN-027",
                        f"$.interfaces[{index}].mate_component",
                        "An interface mate shall reference a scene component.",
                    )
                )
        for index, task in enumerate(scene.get("tasks", [])):
            interface = interfaces.get(task.get("interface"))
            if (
                interface
                and interface.get("component") != task.get("target_component")
            ):
                issues.append(
                    self._issue(
                        "CSR-SCN-028",
                        f"$.tasks[{index}].interface",
                        "The task target shall own the referenced assembly interface.",
                    )
                )
        return issues

    def _payload_paths(self, scene: Scene) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for index, zone in enumerate(scene.get("workzones", [])):
            payload = str(zone.get("payload") or "")
            path = PurePosixPath(payload)
            if (
                zone.get("active")
                and (
                    path.is_absolute()
                    or ".." in path.parts
                    or path.suffix.lower() not in {".usd", ".usda", ".usdc"}
                )
            ):
                issues.append(
                    self._issue(
                        "CSR-SCN-029",
                        f"$.workzones[{index}].payload",
                        "An active payload shall be a safe relative USD path.",
                    )
                )
        return issues

    def _provenance_schema(self, scene: Scene) -> list[ValidationIssue]:
        critical = {"mass_kg", "friction", "tolerance_mm"}
        required = {
            "source",
            "source_type",
            "value",
            "unit",
            "confidence",
            "uncertainty_interval",
            "authority_level",
            "auto_repair_allowed",
        }
        issues: list[ValidationIssue] = []
        for index, record in enumerate(scene.get("provenance", [])):
            if record.get("property") not in critical:
                continue
            missing = sorted(required - set(record))
            interval = record.get("uncertainty_interval")
            value = record.get("value")
            invalid_interval = (
                not isinstance(interval, (list, tuple))
                or len(interval) != 2
                or value is None
                or float(interval[0]) > float(interval[1])
                or not float(interval[0]) <= float(value) <= float(interval[1])
            )
            authority = record.get("authority_level")
            invalid_authority = (
                not isinstance(authority, int) or not 0 <= authority <= 3
            )
            if missing or invalid_interval or invalid_authority:
                details = []
                if missing:
                    details.append(f"missing fields {missing}")
                if invalid_interval:
                    details.append("invalid value/uncertainty interval")
                if invalid_authority:
                    details.append("authority level outside integer range [0, 3]")
                issues.append(
                    self._issue(
                        "CSR-SCN-030",
                        f"$.provenance[{index}]",
                        "Critical-property provenance is incomplete: "
                        + "; ".join(details)
                        + ".",
                    )
                )
        return issues

    def _interface_coordinate_fidelity(self, scene: Scene) -> list[ValidationIssue]:
        """CSR-SCN-031 (contract v0.3.0): member-relative interface coordinates
        shall carry provenance and match the evidence model within the declared
        tolerance.

        Added after the humanoid defect study: coordinate errors inside the
        declared tolerance are invisible to v0.2.0 but measurably degrade
        insertion (docs: readiness-link analysis).
        """
        issues: list[ValidationIssue] = []
        records = scene.get("provenance", [])
        origin_evidence = {
            record.get("entity"): record
            for record in records
            if record.get("property") == "origin_m"
        }
        for index, interface in enumerate(scene.get("interfaces", [])):
            interface_id = interface.get("id")
            path = f"$.interfaces[{index}].origin_m"
            evidence = origin_evidence.get(interface_id)
            if evidence is None:
                issues.append(
                    self._issue(
                        "CSR-SCN-031",
                        path,
                        f"Interface '{interface_id}' origin lacks an evidence "
                        "record (property 'origin_m'); member-relative "
                        "coordinates are unverifiable.",
                    )
                )
                continue
            expected = evidence.get("value")
            origin = interface.get("origin_m")
            tolerance_m = float(interface.get("tolerance_mm") or 0.0) / 1000.0
            if (
                not isinstance(expected, (list, tuple))
                or not isinstance(origin, (list, tuple))
                or len(expected) != 3
                or len(origin) != 3
            ):
                issues.append(
                    self._issue(
                        "CSR-SCN-031",
                        path,
                        f"Interface '{interface_id}' origin or its evidence "
                        "value is not a 3-vector.",
                    )
                )
                continue
            deviation = (
                sum((float(a) - float(b)) ** 2 for a, b in zip(origin, expected))
                ** 0.5
            )
            if deviation > tolerance_m:
                issues.append(
                    self._issue(
                        "CSR-SCN-031",
                        path,
                        f"Interface '{interface_id}' origin deviates "
                        f"{deviation * 1000:.1f} mm from its evidence record, "
                        f"exceeding the declared tolerance "
                        f"{tolerance_m * 1000:.1f} mm.",
                    )
                )
        return issues

    def _interface_clearance_sufficiency(self, scene: Scene) -> list[ValidationIssue]:
        """CSR-SCN-032 (contract v0.3.0): interface clearance shall exceed the
        fastener envelope by the task-required minimum.

        The required minimum is taken from the interface's
        ``required_clearance_mm`` field (task-supplied); interfaces without an
        explicit requirement are not checked (unknown is not a violation, but
        see CSR-SCN-014 for tolerance presence).
        """
        issues: list[ValidationIssue] = []
        for index, interface in enumerate(scene.get("interfaces", [])):
            required = interface.get("required_clearance_mm")
            if required is None:
                continue
            tolerance = interface.get("tolerance_mm")
            if tolerance is None:
                continue  # CSR-SCN-014 reports the missing tolerance
            if float(tolerance) < float(required):
                issues.append(
                    self._issue(
                        "CSR-SCN-032",
                        f"$.interfaces[{index}].tolerance_mm",
                        f"Interface '{interface.get('id')}' clearance "
                        f"{float(tolerance):.2f} mm is below the task-required "
                        f"minimum {float(required):.2f} mm.",
                    )
                )
        return issues
