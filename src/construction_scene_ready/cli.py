"""Command-line entry point for local deterministic validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .validator import SceneValidator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a ConstructionSceneReady JSON scene."
    )
    parser.add_argument("scene", type=Path, help="Path to the scene JSON file")
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the machine-readable validation report",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    with args.scene.open(encoding="utf-8") as handle:
        scene = json.load(handle)

    report = SceneValidator().validate(scene)
    payload = json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
    print(payload)

    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

