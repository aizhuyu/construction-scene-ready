"""Versioned metadata for the Construction Scene Readiness contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    family: str
    severity: str
    safe_auto_repair: bool
    summary: str

    def to_dict(self) -> dict:
        return asdict(self)


def _rule(
    number: int,
    family: str,
    summary: str,
    *,
    safe_auto_repair: bool = True,
) -> RuleDefinition:
    return RuleDefinition(
        rule_id=f"CSR-SCN-{number:03d}",
        family=family,
        severity="critical",
        safe_auto_repair=safe_auto_repair,
        summary=summary,
    )


RULES: tuple[RuleDefinition, ...] = (
    _rule(1, "spatial", "Scene declares a Z-up coordinate frame."),
    _rule(2, "spatial", "Scene units are normalized to metres."),
    _rule(3, "identity", "Every component retains an IFC GUID."),
    _rule(4, "identity", "IFC GUIDs are unique in the scene."),
    _rule(5, "composition", "Every active work zone declares a payload."),
    _rule(6, "composition", "Active assembly zones use interface fidelity."),
    _rule(7, "task", "Task actor resolves to a scene robot."),
    _rule(8, "task", "Task target resolves to a scene component."),
    _rule(9, "state", "Every task declares state preconditions."),
    _rule(10, "task", "Every task declares success criteria."),
    _rule(11, "embodiment", "Robot provides every required task capability."),
    _rule(12, "interface", "Interaction task resolves an assembly interface."),
    _rule(13, "interface", "Assembly interface declares an axis."),
    _rule(14, "interface", "Assembly interface declares a tolerance."),
    _rule(15, "provenance", "Critical properties have provenance records."),
    _rule(16, "provenance", "Provenance confidence lies in [0, 1]."),
    _rule(17, "physics", "Dynamic component mass is positive."),
    _rule(18, "interface", "Assembly-interface axis is normalized."),
    _rule(19, "interface", "Assembly tolerance is positive."),
    _rule(20, "interface", "Assembly interface declares a mate."),
    _rule(21, "state", "Component state belongs to the state vocabulary."),
    _rule(22, "composition", "Component resolves to a declared work zone."),
    _rule(
        23,
        "provenance",
        "Critical property does not rely on unverified model generation.",
        safe_auto_repair=False,
    ),
    _rule(24, "tool", "Assembly task resolves to a scene tool."),
    _rule(25, "tool", "Tool provides every required task capability."),
    _rule(26, "interface", "Interface owner resolves to a component."),
    _rule(27, "interface", "Interface mate resolves to a component."),
    _rule(28, "task", "Task target owns the referenced interface."),
    _rule(29, "composition", "Active payload is a safe relative USD path."),
    _rule(30, "provenance", "Critical provenance follows the typed contract."),
)

RULE_BY_ID = {item.rule_id: item for item in RULES}

