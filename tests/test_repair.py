import copy
import unittest

from construction_scene_ready.fault_injection import generate_fault_set
from construction_scene_ready.repair import WHITELIST, repair_scene


class RepairTest(unittest.TestCase):
    def setUp(self):
        self.scene = {
            "scene_id": "trusted",
            "coordinate_system": {"up_axis": "Z", "meters_per_unit": 1.0},
            "components": [
                {
                    "id": "plate",
                    "ifc_guid": "guid-1",
                    "mass_kg": 1.0,
                    "construction_state": "aligned",
                    "workzone_id": "zone_a",
                },
                {
                    "id": "frame",
                    "ifc_guid": "guid-2",
                    "mass_kg": 2.0,
                    "construction_state": "temporarily_fixed",
                    "workzone_id": "zone_a",
                },
            ],
            "robots": [{"id": "g1", "capabilities": ["bimanual"]}],
            "tools": [
                {
                    "id": "parallel_gripper",
                    "capabilities": ["grasp", "insertion"],
                }
            ],
            "workzones": [
                {
                    "id": "zone_a",
                    "active": True,
                    "payload": "zone.usda",
                    "interaction_lod": "interface",
                }
            ],
            "interfaces": [
                {
                    "id": "plate_hole",
                    "component": "plate",
                    "axis": [0, 0, 1],
                    "tolerance_mm": 1.0,
                    "mate_component": "frame",
                }
            ],
            "tasks": [
                {
                    "id": "insert",
                    "type": "insert",
                    "actor": "g1",
                    "target_component": "plate",
                    "interface": "plate_hole",
                    "tool": "parallel_gripper",
                    "preconditions": ["aligned"],
                    "success_criteria": ["inserted"],
                    "required_capabilities": ["bimanual"],
                    "required_tool_capabilities": ["insertion"],
                }
            ],
            "provenance": [
                {
                    "entity": "plate",
                    "property": "mass_kg",
                    "source": "trusted_scene",
                    "source_type": "explicit_ifc",
                    "value": 1.0,
                    "unit": "kg",
                    "confidence": 1.0,
                    "uncertainty_interval": [1.0, 1.0],
                    "authority_level": 3,
                    "auto_repair_allowed": False,
                },
                {
                    "entity": "contact",
                    "property": "friction",
                    "source": "material_database",
                    "confidence": 0.8,
                    "source_type": "material_database",
                    "value": 0.5,
                    "unit": "dimensionless",
                    "uncertainty_interval": [0.3, 0.7],
                    "authority_level": 2,
                    "auto_repair_allowed": False,
                },
                {
                    "entity": "plate_hole",
                    "property": "tolerance_mm",
                    "source": "trusted_scene",
                    "source_type": "engineering_rule",
                    "value": 1.0,
                    "unit": "mm",
                    "confidence": 1.0,
                    "uncertainty_interval": [1.0, 1.0],
                    "authority_level": 2,
                    "auto_repair_allowed": False,
                },
            ],
        }

    def test_safe_faults_are_repaired_and_unsupported_sources_escalate(self):
        for faulty in generate_fault_set(self.scene):
            with self.subTest(fault=faulty["fault_ground_truth"]["fault"]):
                repaired, audit = repair_scene(faulty, self.scene)
                if "unsupported_generated_friction" in faulty[
                    "fault_ground_truth"
                ]["members"]:
                    self.assertFalse(audit["accepted"])
                    self.assertIn("CSR-SCN-023", audit["blocked_rule_ids"])
                else:
                    self.assertTrue(audit["accepted"])
                    self.assertTrue(audit["events"])
                self.assertEqual(repaired["scene_id"], faulty["scene_id"])

    def test_whitelist_covers_only_declared_tools(self):
        self.assertEqual(len(WHITELIST), 30)
        self.assertEqual(len(set(name for name, _ in WHITELIST.values())), 30)
