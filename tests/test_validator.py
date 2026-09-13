from __future__ import annotations

import json
import unittest
from pathlib import Path

from construction_scene_ready import SceneValidator


ROOT = Path(__file__).resolve().parents[1]


class SceneValidatorTest(unittest.TestCase):
    def load_scene(self, name: str) -> dict:
        path = ROOT / "examples" / name
        return json.loads(path.read_text(encoding="utf-8"))

    def test_minimal_scene_passes(self) -> None:
        report = SceneValidator().validate(self.load_scene("minimal_scene.json"))
        self.assertTrue(report.passed)
        self.assertEqual(report.issues, ())

    def test_faulty_scene_exposes_scene_level_defects(self) -> None:
        report = SceneValidator().validate(self.load_scene("faulty_scene.json"))
        self.assertFalse(report.passed)
        rule_ids = {issue.rule_id for issue in report.issues}
        self.assertTrue(
            {
                "CSR-SCN-001",
                "CSR-SCN-002",
                "CSR-SCN-004",
                "CSR-SCN-005",
                "CSR-SCN-006",
                "CSR-SCN-007",
                "CSR-SCN-008",
                "CSR-SCN-009",
                "CSR-SCN-010",
                "CSR-SCN-011",
                "CSR-SCN-012",
                "CSR-SCN-015",
                "CSR-SCN-016",
            }.issubset(rule_ids)
        )

    def test_report_is_machine_readable(self) -> None:
        report = SceneValidator().validate(self.load_scene("faulty_scene.json"))
        encoded = json.dumps(report.to_dict())
        self.assertIn("CSR-SCN-012", encoded)


if __name__ == "__main__":
    unittest.main()

