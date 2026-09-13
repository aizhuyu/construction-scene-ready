"""Export the versioned rule registry to a supplementary CSV."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from construction_scene_ready.rule_registry import RULES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/scene-readiness-rules.csv"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "rule_id",
                "family",
                "severity",
                "safe_auto_repair",
                "summary",
            ),
        )
        writer.writeheader()
        writer.writerows(item.to_dict() for item in RULES)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

