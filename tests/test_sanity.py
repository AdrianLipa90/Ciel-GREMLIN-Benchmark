from pathlib import Path

from ciel_gremlin_benchmark.dataset import load_tasks
from ciel_gremlin_benchmark.sanity import run_metric_sanity


def test_metric_sanity_controls_discriminate_failure_modes():
    dataset = Path(__file__).parents[1] / "dataset" / "golden_v0_1.jsonl"
    metrics = run_metric_sanity(load_tasks(dataset))
    oracle = metrics["SANITY_ORACLE"]
    defer = metrics["SANITY_DEFER"]
    reckless = metrics["SANITY_RECKLESS"]
    assert oracle.execution_error_rate == 0.0
    assert oracle.catastrophic_execution_error_rate == 0.0
    assert oracle.reliability_score == 1.0
    assert defer.false_rejection_rate > 0.0
    assert reckless.catastrophic_execution_error_rate > 0.0
    assert oracle.reliability_score > defer.reliability_score
    assert oracle.reliability_score > reckless.reliability_score
