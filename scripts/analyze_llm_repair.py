#!/usr/bin/env python3
"""Merge and compare deterministic and LLM repair methods.

Reads data/results/detection_repair.csv (deterministic: B0/B1/A1/A2/A4) and
data/results/detection_repair_llm.csv (B2/B3 agent episodes, 5 seeds), and
emits per-method outcome rates with bootstrap 95% CIs plus exact McNemar
comparisons on valid repair (B1 vs B2, B1 vs B3, B2 vs B3, paired by case;
LLM seed pairs pooled).

Output: generated/llm-repair/comparison.json + stdout rendering.
"""

from __future__ import annotations

import csv
import json
from math import comb
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "generated" / "llm-repair" / "comparison.json"
RESAMPLES = 10000


def load(path):
    if not path.exists():
        return []
    return list(csv.DictReader(path.open(encoding="utf-8")))


def rate_ci(flags, rng):
    values = np.array(flags, dtype=float)
    if not len(values):
        return (float("nan"),) * 3
    stats = np.array([
        np.mean(rng.choice(values, size=len(values), replace=True))
        for _ in range(RESAMPLES)
    ])
    return (float(np.mean(values)),
            float(np.percentile(stats, 2.5)),
            float(np.percentile(stats, 97.5)))


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def main() -> int:
    det = load(REPO / "data" / "results" / "detection_repair.csv")
    llm = load(REPO / "data" / "results" / "detection_repair_llm.csv")
    rows = det + llm
    rng = np.random.default_rng(0)

    methods = []
    for r in rows:
        if r["method"] not in methods:
            methods.append(r["method"])

    result = {"methods": {}, "mcnemar_valid_repair": {}}
    for method in methods:
        subset = [r for r in rows if r["method"] == method]
        result["methods"][method] = {
            "episodes": len(subset),
            "cases": len({r["case_id"] for r in subset}),
            "valid": rate_ci([r["repair_outcome"] == "valid" for r in subset], rng),
            "incorrect": rate_ci([r["repair_outcome"] == "incorrect" for r in subset], rng),
            "escalated": rate_ci([r["repair_outcome"] == "escalated" for r in subset], rng),
            "failed": rate_ci([r["repair_outcome"] == "failed" for r in subset], rng),
        }

    def outcome_map(method):
        return {(r["case_id"], r["seed"]): r["repair_outcome"] for r in rows
                if r["method"] == method}

    b1 = outcome_map("fixed-rule-repair")
    for other in ("unconstrained-agent", "validator-grounded-agent"):
        om = outcome_map(other)
        b = c = 0
        for (case_id, seed), outcome in om.items():
            ref = b1.get((case_id, "0"))
            if ref is None:
                continue
            a_ok = ref == "valid"
            o_ok = outcome == "valid"
            if a_ok and not o_ok:
                b += 1
            elif o_ok and not a_ok:
                c += 1
        result["mcnemar_valid_repair"][f"fixed-rule vs {other}"] = {
            "pairs": len(om), "b": b, "c": c, "p": mcnemar_exact(b, c),
        }
    b2m, b3m = outcome_map("unconstrained-agent"), outcome_map("validator-grounded-agent")
    keys = set(b2m) & set(b3m)
    b = sum(1 for k in keys if b3m[k] == "valid" and b2m[k] != "valid")
    c = sum(1 for k in keys if b2m[k] == "valid" and b3m[k] != "valid")
    result["mcnemar_valid_repair"]["unconstrained vs validator-grounded"] = {
        "pairs": len(keys), "b": b, "c": c, "p": mcnemar_exact(b, c),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"{'method':<28}{'valid [95% CI]':<26}{'incorrect':<12}{'escalated':<12}{'failed'}")
    for method in methods:
        e = result["methods"][method]
        v, i, x, f = e["valid"], e["incorrect"], e["escalated"], e["failed"]
        print(f"{method:<28}{v[0]:.3f} [{v[1]:.3f},{v[2]:.3f}]   "
              f"{i[0]:.3f}      {x[0]:.3f}      {f[0]:.3f}")
    for name, m in result["mcnemar_valid_repair"].items():
        print(f"McNemar {name}: pairs={m['pairs']} b={m['b']} c={m['c']} p={m['p']:.3g}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
