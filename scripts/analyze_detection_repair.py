#!/usr/bin/env python3
"""Statistics for the registered detection/repair results.

Reads data/results/detection_repair.csv and emits, per method:
- case-level detection / valid-repair / escalation rates with bootstrap 95% CIs
- rule-level micro precision/recall with bootstrap 95% CIs (cases resampled)
- exact McNemar test between B0 and B1 on per-case detection

Output: generated/detection-repair/<run_id>/analysis.json plus a LaTeX-ready
stdout rendering for paper/sections/07-results.tex.
"""

from __future__ import annotations

import argparse
import csv
import json
from math import comb
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]


def bootstrap_ci(values: np.ndarray, stat, resamples: int, rng) -> tuple[float, float, float]:
    point = stat(values)
    if len(values) == 0:
        return point, float("nan"), float("nan")
    stats = np.array([
        stat(rng.choice(values, size=len(values), replace=True))
        for _ in range(resamples)
    ])
    return point, float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def rate_ci(rows: list[dict], key: str, resamples: int, rng) -> tuple[float, float, float]:
    values = np.array([int(r[key]) for r in rows], dtype=float)
    return bootstrap_ci(values, np.mean, resamples, rng)


def rule_metric_ci(rows: list[dict], resamples: int, rng) -> dict[str, tuple[float, float, float]]:
    def micro(subset, kind):
        tp = sum(int(r["true_positive"]) for r in subset)
        fp = sum(int(r["false_positive"]) for r in subset)
        fn = sum(int(r["false_negative"]) for r in subset)
        if kind == "precision":
            return tp / (tp + fp) if tp + fp else float("nan")
        return tp / (tp + fn) if tp + fn else float("nan")

    def stat_factory(kind):
        def stat(indices):
            subset = [rows[int(i)] for i in indices]
            return micro(subset, kind)
        return stat

    out = {}
    index = np.arange(len(rows), dtype=float)
    for kind in ("precision", "recall"):
        point = micro(rows, kind)
        stats = np.array([
            stat_factory(kind)(rng.choice(index, size=len(index), replace=True))
            for _ in range(resamples)
        ])
        stats = stats[~np.isnan(stats)]
        lo, hi = (float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))) if len(stats) else (float("nan"), float("nan"))
        out[kind] = (point, lo, hi)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="B-CPU-DETREp-0001")
    parser.add_argument("--resamples", type=int, default=10000)
    args = parser.parse_args()

    rows = list(csv.DictReader((REPO / "data" / "results" / "detection_repair.csv").open(encoding="utf-8")))
    rng = np.random.default_rng(0)
    methods = []
    for row in rows:
        if row["method"] not in methods:
            methods.append(row["method"])

    analysis: dict = {"run_id": args.run_id, "resamples": args.resamples, "methods": {}}
    for method in methods:
        subset = [r for r in rows if r["method"] == method]
        entry = {
            "cases": len(subset),
            "detected": rate_ci(subset, "detected", args.resamples, rng),
            "valid_repair": rate_ci(subset, "valid_repair", args.resamples, rng),
            "escalated": rate_ci(subset, "escalated", args.resamples, rng),
            "rule_level": rule_metric_ci(subset, args.resamples, rng),
        }
        per_partition = {}
        for partition in sorted({r["partition"] for r in subset}):
            prows = [r for r in subset if r["partition"] == partition]
            per_partition[partition] = {
                "cases": len(prows),
                "detected": rate_ci(prows, "detected", args.resamples, rng),
                "valid_repair": rate_ci(prows, "valid_repair", args.resamples, rng),
            }
        entry["partitions"] = per_partition
        analysis["methods"][method] = entry

    b0 = {(r["partition"], r["scene_id"], r["fault_id"]): int(r["detected"])
          for r in rows if r["method"] == "direct-conversion"}
    b1 = {(r["partition"], r["scene_id"], r["fault_id"]): int(r["detected"])
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
