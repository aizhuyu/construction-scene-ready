"""Frozen benchmark partitions (development / test / challenge).

The partition manifest is derived deterministically from
``docs/fault-taxonomy.csv`` (the ``challenge_role`` column) and the
reproducible variant design in ``fixtures.variant_designs``.  The manifest is
written once, committed, and hashed; experiment runners consume it read-only
so that no later code change can silently move a fault between partitions.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

MANIFEST_VERSION = "1.0.0"

#: Scene assignment per partition.  Development runs on the three base
#: fixtures; test and challenge run on variant index 1 (geometry differs from
#: development, as required by docs/baseline-protocol.md).
SCENE_ASSIGNMENT = {
    "development": {"scene_kind": "base", "variant_index": 0},
    "test": {"scene_kind": "variant", "variant_index": 1},
    "challenge": {"scene_kind": "variant", "variant_index": 1},
}


def load_fault_roles(taxonomy_path: Path) -> dict[str, dict[str, str]]:
    """Read docs/fault-taxonomy.csv into {fault_id: row} preserving order."""
    with taxonomy_path.open(newline="", encoding="utf-8") as handle:
        return {row["fault_id"]: row for row in csv.DictReader(handle)}


def build_manifest(taxonomy_path: Path) -> dict[str, Any]:
    """Build the frozen partition manifest from the frozen taxonomy."""
    roles = load_fault_roles(taxonomy_path)
    partitions: dict[str, list[str]] = {"development": [], "test": [], "challenge": []}
    for fault_id, row in roles.items():
        role = row["challenge_role"]
        if role not in partitions:
            raise ValueError(f"Unknown challenge_role {role!r} for fault {fault_id!r}")
        partitions[role].append(fault_id)
    return {
        "manifest_version": MANIFEST_VERSION,
        "taxonomy_sha256": hashlib.sha256(taxonomy_path.read_bytes()).hexdigest(),
        "partitions": {
            role: {"faults": faults, **SCENE_ASSIGNMENT[role]}
            for role, faults in partitions.items()
        },
    }


def write_manifest(manifest: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    output_path.write_text(payload, encoding="utf-8")


def load_manifest(manifest_path: Path, taxonomy_path: Path) -> dict[str, Any]:
    """Load a frozen manifest and verify it still matches the taxonomy."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = build_manifest(taxonomy_path)
    if manifest != expected:
        raise ValueError(
            f"Partition manifest {manifest_path} is stale: it no longer matches "
            f"{taxonomy_path}. Freeze a new manifest explicitly rather than "
            f"editing partitions by hand."
        )
    return manifest
