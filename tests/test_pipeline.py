from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


HAS_IFC = importlib.util.find_spec("ifcopenshell") is not None
HAS_USD = importlib.util.find_spec("pxr") is not None


@unittest.skipUnless(HAS_IFC and HAS_USD, "IfcOpenShell and OpenUSD required")
class LocalPipelineTest(unittest.TestCase):
    def test_three_ifc_scenes_compile_and_faults_fail(self) -> None:
        from construction_scene_ready.pipeline import run_pipeline

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            summary = run_pipeline(root)
            self.assertEqual(len(summary["scenes"]), 3)
            for scene in summary["scenes"]:
                self.assertTrue(scene["passed"])
                self.assertTrue(Path(scene["ifc"]).exists())
                self.assertTrue(Path(scene["cewg"]).exists())
                self.assertTrue(Path(scene["usd"]).exists())
                self.assertEqual(len(scene["faults"]), 35)
                self.assertTrue(
                    all(not fault["passed"] for fault in scene["faults"])
                )

    def test_composed_usd_has_global_reference_and_workzone_payload(self) -> None:
        from pxr import Usd, UsdGeom, UsdPhysics

        from construction_scene_ready.pipeline import run_pipeline

        with tempfile.TemporaryDirectory() as temporary:
            summary = run_pipeline(Path(temporary))
            root_path = Path(summary["scenes"][0]["usd"])
            all_loaded_path = root_path.with_name(
                "building_root_all_loaded.usda"
            )
            self.assertTrue(all_loaded_path.exists())
            stage = Usd.Stage.Open(str(root_path), load=Usd.Stage.LoadNone)
            self.assertTrue(stage.GetPrimAtPath("/World/Global"))
            self.assertTrue(stage.GetPrimAtPath("/World/WorkZones/zone_a"))

            stage.Load()
            component = stage.GetPrimAtPath(
                "/World/WorkZones/zone_a/Components/connection_plate"
            )
            self.assertTrue(component)
            self.assertTrue(component.HasAPI(UsdPhysics.CollisionAPI))
            self.assertTrue(component.HasAPI(UsdPhysics.RigidBodyAPI))
            self.assertTrue(component.HasAPI(UsdPhysics.MassAPI))
            self.assertEqual(
                [
                    operation.GetOpName()
                    for operation in UsdGeom.Xformable(
                        component
                    ).GetOrderedXformOps()
                ],
                [
                    "xformOp:translate",
                    "xformOp:orient",
                    "xformOp:scale",
                ],
            )
            self.assertEqual(
                component.GetAttribute("csr:fidelity").Get(),
                "workzone_physics",
            )
            self.assertEqual(
                component.GetAttribute(
                    "csr:provenance:mass_kg:source_type"
                ).Get(),
                "explicit_ifc",
            )
            interaction = stage.GetPrimAtPath(
                "/World/Tasks/position_plate/Interaction/"
                "plate_member_alignment"
            )
            self.assertTrue(interaction)
            self.assertEqual(
                interaction.GetAttribute("csr:interfaceType").Get(),
                "align",
            )
            all_loaded = Usd.Stage.Open(
                str(all_loaded_path), load=Usd.Stage.LoadAll
            )
            task_activated = Usd.Stage.Open(
                str(root_path), load=Usd.Stage.LoadAll
            )
            self.assertGreater(
                sum(1 for _ in all_loaded.Traverse()),
                sum(1 for _ in task_activated.Traverse()),
            )


if __name__ == "__main__":
    unittest.main()
