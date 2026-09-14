#!/usr/bin/env python3
"""fig09 case study: auditable fault -> diagnosis -> escalation sequence.

All panels render TRUE committed artefacts of one held-out challenge case
(unsupported_generated_friction on pin_insertion__v001): the faulted
provenance record, the validator's typed finding, and the frozen model's
validator-grounded escalation recorded in the episode ledger.  Simulator
frames are pending (Isaac Sim 4.2 offscreen rendering issue; see
docs/experiment-registry.csv RTX-0001 notes).

Output: paper/figures/fig09_case_study.{pdf,png}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from construction_scene_ready.fault_injection import inject_fault  # noqa: E402
from construction_scene_ready.suites import build_scenes  # noqa: E402
from construction_scene_ready.validator import SceneValidator  # noqa: E402

import tempfile
import textwrap


def _fmt(text: str, width: int = 44, max_lines: int = 20) -> str:
    lines = []
    for raw in text.split("\n"):
        lines += textwrap.wrap(raw, width=width,
                               subsequent_indent="  ") or [""]
    return "\n".join(lines[:max_lines])


def main() -> int:
    fault_id = "unsupported_generated_friction"
    with tempfile.TemporaryDirectory() as tmp:
        scenes = build_scenes("variant", 1, Path(tmp))
    scene = next(s for s in scenes if s["scene_id"].startswith("pin_insertion"))
    faulty = inject_fault(scene, fault_id)
    validator = SceneValidator()
    issues = [i.to_dict() for i in validator.validate(faulty).issues]

    # 故障注入点: 被污染的 friction provenance 记录
    tainted = [r for r in faulty["provenance"] if r.get("property") == "friction"]

    ledger = [
        json.loads(line)
        for line in (REPO / "generated" / "llm-repair" / "episodes.jsonl").open(encoding="utf-8")
    ]
    esc = [r for r in ledger if r["fault_id"] == fault_id
           and r["method"] == "validator-grounded-agent"
           and r["outcome"] == "escalated"]

    fig, axes = plt.subplots(1, 3, figsize=(7.5, 3.1))
    panels = [
        ("(a) faulted evidence record (friction)",
         _fmt(json.dumps(tainted, indent=1))),
        ("(b) typed validator finding (CSR-SCN-023)",
         _fmt(json.dumps(issues, indent=1))),
        ("(c) validator-grounded agent escalation",
         _fmt(json.dumps({
             "method": esc[0]["method"],
             "case": f"{esc[0]['scene_id']}__{esc[0]['fault_id']}",
             "outcome": esc[0]["outcome"],
             "episodes_escalated": f"{len(esc)}/15 (3 scenes x 5 seeds)",
             "note": "no authoritative friction source; "
                     "repair refused rather than invented",
         }, indent=1))),
    ]
    for ax, (title, text) in zip(axes, panels):
        ax.axis("off")
        ax.set_title(title, fontsize=7, loc="left")
        ax.text(0.0, 0.98, text, family="monospace", fontsize=5.2,
                va="top", ha="left",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#F4F4F4",
                          edgecolor="#888888", linewidth=0.6))
    fig.subplots_adjust(left=0.01, right=0.99, top=0.88, bottom=0.02, wspace=0.04)
    out = REPO / "paper" / "figures"
    for ext in ("pdf", "png"):
        fig.savefig(out / f"fig09_case_study.{ext}", dpi=600)
    print("wrote fig09_case_study.{pdf,png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
