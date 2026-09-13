"""Small dependency-free result models used by the first local milestone."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ValidationIssue:
    rule_id: str
    severity: str
    path: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationReport:
    scene_id: str
    issues: tuple[ValidationIssue, ...]

    @property
    def passed(self) -> bool:
        return not any(issue.severity == "critical" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "passed": self.passed,
            "issue_count": len(self.issues),
            "issues": [issue.to_dict() for issue in self.issues],
        }

