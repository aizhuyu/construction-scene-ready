"""Deterministic structural metrics for composed OpenUSD stages."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def inspect_composition(root_path: Path) -> dict[str, Any]:
    """Inspect a fully loaded stage without reporting unstable timings."""

    from pxr import Usd, UsdPhysics

    stage = Usd.Stage.Open(str(root_path), load=Usd.Stage.LoadAll)
    if stage is None:
        raise ValueError(f"Unable to open USD stage: {root_path}")
    prims = list(stage.Traverse())
    used_layers = []
    total_layer_bytes = 0
    for layer in sorted(
        stage.GetUsedLayers(),
        key=lambda item: item.identifier,
    ):
        if not layer.realPath and layer.identifier.startswith("anon:"):
            continue
        real_path = Path(layer.realPath) if layer.realPath else None
        size_bytes = (
            real_path.stat().st_size
            if real_path is not None and real_path.exists()
            else 0
        )
        total_layer_bytes += size_bytes
        used_layers.append(
            {
                "identifier": real_path.name if real_path else layer.identifier,
                "size_bytes": size_bytes,
            }
        )
    world = stage.GetPrimAtPath("/World")
    return {
        "root_file": root_path.name,
        "composition_mode": (
            world.GetAttribute("csr:compositionMode").Get() if world else None
        ),
        "prim_count": len(prims),
        "payload_prim_count": sum(prim.HasPayload() for prim in prims),
        "rigid_body_count": sum(
            prim.HasAPI(UsdPhysics.RigidBodyAPI) for prim in prims
        ),
        "collision_api_count": sum(
            prim.HasAPI(UsdPhysics.CollisionAPI) for prim in prims
        ),
        "used_layer_count": len(used_layers),
        "used_layer_bytes": total_layer_bytes,
        "used_layers": used_layers,
    }


def compare_compositions(
    task_activated_root: Path,
    all_loaded_root: Path,
) -> dict[str, Any]:
    task_activated = inspect_composition(task_activated_root)
    all_loaded = inspect_composition(all_loaded_root)

    def reduction(metric: str) -> float:
        baseline = float(all_loaded[metric])
        return (
            (baseline - float(task_activated[metric])) / baseline
            if baseline
            else 0.0
        )

    return {
        "task_activated": task_activated,
        "all_loaded": all_loaded,
        "reduction": {
            "prim_count": reduction("prim_count"),
            "rigid_body_count": reduction("rigid_body_count"),
            "collision_api_count": reduction("collision_api_count"),
            "used_layer_bytes": reduction("used_layer_bytes"),
        },
    }
