"""CIEL × GREMLIN Benchmark v0.1."""

from .dataset import load_tasks, validate_dataset
from .receipts import canonical_sha256, seal_receipt, verify_receipt
from .runner import BenchmarkRunner, ReplayAdapter
from .schema import Decision, Family, Prediction, Task
from .scoring import AggregateMetrics, TaskScore, aggregate_scores, score_prediction

__all__ = [
    "AggregateMetrics",
    "BenchmarkRunner",
    "Decision",
    "Family",
    "Prediction",
    "ReplayAdapter",
    "Task",
    "TaskScore",
    "aggregate_scores",
    "canonical_sha256",
    "load_tasks",
    "score_prediction",
    "seal_receipt",
    "validate_dataset",
    "verify_receipt",
]
