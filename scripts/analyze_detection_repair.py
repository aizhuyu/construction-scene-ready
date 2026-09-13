#!/usr/bin/env python3
"""Statistics for the registered detection/repair results.

Reads data/results/detection_repair.csv (registered tidy schema) and emits,
per method:
- case-level detection / valid-repair / escalation rates with bootstrap 95% CIs
- rule-level micro precision/recall with bootstrap 95% CIs (cases resampled)
- exact McNemar test between B0 and B1 on per-case detection

Output: generated/detection-repair/<run_id>/analysis.json plus a readable
stdout rendering for the manuscript results tables.
"""

from __future__ import annotations

import argparse
import csv
import json
from math import comb
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]


def rate_ci(rows: list[dict], pred, resamples: int, rng) -> tuple[float, float, float]:
    values = np.array([1.0 if pred(r) else 0.0 for r in rows])
    point = float(np.mean(values)) if len(values) else float("nan")
    if not len(values):
        return point, float("nan"), float("nan")
    stats = np.array([
        float(np.mean(rng.choice(values, size=len(values), replace=True)))
        for _ in range(resamples)
    ])
    return point, float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def rule_metric_ci(rows: list[dict], resamples: int, rng) -> dict[str, tuple[float, float, float]]:
    def micro(subset, kind):
        tp = sum(int(r["tp"]) for r in subset)
        fp = sum(int(r["fp"]) for r in subset)
        fn = sum(int(r["fn"]) for r in subset)
        if kind == "precision":
            return tp / (tp + fp) if tp + fp else float("nan")
        return tp / (tp + fn) if tp + fn else float("nan")

    out = {}
    index = np.arange(len(rows))
    for kind in ("precision", "recall"):
        point = micro(rows, kind)
        stats = np.array([
            micro([rows[int(i)] for i in rng.choice(index, size=len(index), replace=True)], kind)
            for _ in range(resamples)
        ])
        stats = stats[~np.isnan(stats)]
        lo, hi = (
            (float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5)))
            if len(stats) else (float("nan"), float("nan"))
        )
        out[kind] = (point, lo, hi)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="B-CPU-DETREp-0001")
    parser.add_argument("--resamples", type=int, default=10000)
    args = parser.parse_args()

    rows = list(csv.DictReader(
        (REPO / "data" / "results" / "detection_repair.csv").open(encoding="utf-8")
    ))
    rng = np.random.default_rng(0)
    methods = []
    for row in rows:
        if row["method"] not in methods:
            methods.append(row["method"])

    preds = {
        "detected": lambda r: r["critical_detected"] == "1",
        "valid_repair": lambda r: r["repair_outcome"] == "valid",
        "escalated": lambda r: r["repair_outcome"] == "escalated",
    }
    analysis: dict = {"run_id": args.run_id, "resamples": args.resamples, "methods": {}}
    for method in methods:
        subset = [r for r in rows if r["method"] == method]
        entry = {"cases": len(subset)}
        for name, pred in preds.items():
            entry[name] = rate_ci(subset, pred, args.resamples, rng)
        entry["rule_level"] = rule_metric_ci(subset, args.resamples, rng)
        entry["partitions"] = {
            partition: {
                "cases": len(prows),
                "detected": rate_ci(prows, preds["detected"], args.resamples, rng),
                "valid_repair": rate_ci(prows, preds["valid_repair"], args.resamples, rng),
            }
            for partition in sorted({r["partition"] for r in subset})
            for prows in [[r for r in subset if r["partition"] == partition]]
        }
        analysis["methods"][method] = entry

    key_of = lambda r: (r["partition"], r["scenario"], r["case_id"])
    b0 = {key_of(r): r["critical_detected"] == "1"
          for r in rows if r["method"] == "direct-conversion"}
    b1 = {key_of(r): r["critical_detected"] == "1"
          for r in rows if r["method"] == "fixed-rule-repair"}
    keys = sorted(set(b0) & set(b1))
    b = sum(1 for k in keys if b1[k] and not b0[k])
    c = sum(1 for k in keys if b0[k] and not b1[k])
    analysis["mcnemar_b0_vs_b1"] = {"paired": len(keys), "b": b, "c": c, "p": mcnemar_exact(b, c)}

    out = REPO / "generated" / "detection-repair" / args.run_id / "analysis.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")

    print(f"{'method':<30}{'detected [95% CI]':<26}{'valid repair [95% CI]':<26}{'escalated':<10}")
    for method in methods:
        e = analysis["methods"][method]
        d, v, x = e["detected"], e["valid_repair"], e["escalated"]
        print(f"{method:<30}{d[0]:.3f} [{d[1]:.3f},{d[2]:.3f}]   "
              f"{v[0]:.3f} [{v[1]:.3f},{v[2]:.3f}]   {x[0]:.3f}")
    m = analysis["mcnemar_b0_vs_b1"]
    print(f"McNemar B0 vs B1: paired={m['paired']} b={m['b']} c={m['c']} p={m['p']:.3g}")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
