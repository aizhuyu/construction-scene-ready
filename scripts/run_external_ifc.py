#!/usr/bin/env python3
"""R4: compile and validate a real third-party IFC model (no CSR annotations).

Uses the buildingSMART IFC 4.3 ADD2 sample (Building-Architecture.ifc,
data/external/).  The compiler skips elements without Pset_CSR_* annotations
by design, so the interesting question is what the contract says about the
resulting scene.  Writes generated/external-ifc/report.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from construction_scene_ready.ifc_parser import compile_ifc  # noqa: E402
from construction_scene_ready.validator import SceneValidator  # noqa: E402

IFC = REPO / "data" / "external" / "Building-Architecture.ifc"


def main() -> int:
    import ifcopenshell  # element census for context
    model = ifcopenshell.open(str(IFC))
    census = {}
    for etype in ("IfcElement", "IfcSpace", "IfcTask", "IfcConstructionEquipmentResource"):
        census[etype] = len(model.by_type(etype))

    scene = compile_ifc(IFC)
    report = SceneValidator().validate(scene)
    out = {
        "ifc_file": IFC.name,
        "ifc_schema": model.schema,
        "element_census": census,
        "compiled": {
            "scene_id": scene["scene_id"],
            "components": len(scene["components"]),
            "interfaces": len(scene["interfaces"]),
            "workzones": len(scene["workzones"]),
            "tasks": len(scene["tasks"]),
            "provenance_records": len(scene["provenance"]),
        },
        "validation": report.to_dict(),
    }
    out_path = REPO / "generated" / "external-ifc" / "report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
