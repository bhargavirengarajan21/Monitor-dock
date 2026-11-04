"""Story 26 — eval script: hit rate, honest misses, latency.

Acceptance criteria: Running the script prints hit rate at 3 on 30 alerts,
honest-miss rate on 10 unseen alerts and p50/p95 answer latency; results go
into the README.

Usage:
    python scripts/eval.py [path/to/alerts.json]

The eval set is a JSON file with two lists:
    "alerts_with_match": [{ "alert", "expected_incident", "retrieved": [ids...], "latency_ms" }]
    "alerts_without_match": [{ "alert", "answer_no_match": bool, "latency_ms" }]

This script computes the metrics offline from recorded retrieval results, so it
runs in CI without any live model or database.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import List


def hit_rate_at_k(alerts_with_match: List[dict], k: int = 3) -> float:
    if not alerts_with_match:
        return 0.0
    hits = 0
    for case in alerts_with_match:
        top_k = case.get("retrieved", [])[:k]
        if case.get("expected_incident") in top_k:
            hits += 1
    return hits / len(alerts_with_match)


def honest_miss_rate(alerts_without_match: List[dict]) -> float:
    if not alerts_without_match:
        return 0.0
    correct = sum(1 for case in alerts_without_match if case.get("answer_no_match") is True)
    return correct / len(alerts_without_match)


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    # Nearest-rank method: rank = ceil(pct/100 * N), clamped to [1, N].
    rank = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def run(dataset: dict) -> dict:
    with_match = dataset.get("alerts_with_match", [])
    without_match = dataset.get("alerts_without_match", [])
    latencies = [
        case["latency_ms"]
        for case in (*with_match, *without_match)
        if "latency_ms" in case
    ]
    return {
        "alerts_with_match": len(with_match),
        "alerts_without_match": len(without_match),
        "hit_rate_at_3": round(hit_rate_at_k(with_match, 3), 3),
        "honest_miss_rate": round(honest_miss_rate(without_match), 3),
        "latency_p50_ms": round(percentile(latencies, 50), 1),
        "latency_p95_ms": round(percentile(latencies, 95), 1),
    }


def format_report(metrics: dict) -> str:
    return (
        "Incident Memory — evaluation\n"
        f"  Alerts with a known incident : {metrics['alerts_with_match']}\n"
        f"  Alerts with no match         : {metrics['alerts_without_match']}\n"
        f"  Hit rate @3                  : {metrics['hit_rate_at_3']:.1%}\n"
        f"  Honest misses                : {metrics['honest_miss_rate']:.1%}\n"
        f"  Answer latency p50           : {metrics['latency_p50_ms']:.1f} ms\n"
        f"  Answer latency p95           : {metrics['latency_p95_ms']:.1f} ms"
    )


def main(argv: List[str]) -> int:
    default = Path(__file__).resolve().parent.parent / "eval" / "alerts.json"
    path = Path(argv[1]) if len(argv) > 1 else default
    if not path.exists():
        print(f"Eval dataset not found: {path}", file=sys.stderr)
        return 1
    dataset = json.loads(path.read_text(encoding="utf-8"))
    metrics = run(dataset)
    print(format_report(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
