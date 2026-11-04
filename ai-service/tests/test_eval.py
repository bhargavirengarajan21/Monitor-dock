"""Story 26 — eval script metrics."""

import json
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import eval as eval_script  # noqa: E402


def test_hit_rate_at_k():
    cases = [
        {"expected_incident": "a", "retrieved": ["a", "b", "c"]},  # hit
        {"expected_incident": "x", "retrieved": ["b", "c", "x"]},  # hit (rank 3)
        {"expected_incident": "y", "retrieved": ["b", "c", "d"]},  # miss
    ]
    assert eval_script.hit_rate_at_k(cases, 3) == 2 / 3


def test_honest_miss_rate():
    cases = [{"answer_no_match": True}, {"answer_no_match": True}, {"answer_no_match": False}]
    assert eval_script.honest_miss_rate(cases) == 2 / 3


def test_percentiles():
    values = [100, 200, 300, 400, 500]
    assert eval_script.percentile(values, 50) == 300
    assert eval_script.percentile(values, 95) == 500


def test_run_on_bundled_dataset():
    path = Path(__file__).resolve().parent.parent / "eval" / "alerts.json"
    dataset = json.loads(path.read_text(encoding="utf-8"))
    metrics = eval_script.run(dataset)
    assert metrics["alerts_with_match"] == 30
    assert metrics["alerts_without_match"] == 10
    # dataset is constructed for a 0.9 hit rate and 0.9 honest-miss rate
    assert metrics["hit_rate_at_3"] == 0.9
    assert metrics["honest_miss_rate"] == 0.9
    assert metrics["latency_p95_ms"] >= metrics["latency_p50_ms"]
