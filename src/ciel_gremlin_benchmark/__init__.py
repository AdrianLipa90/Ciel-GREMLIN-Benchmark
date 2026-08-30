"""CIEL × GREMLIN Benchmark v0.1."""

from .capture import capture_predictions
from .dataset import dataset_sha256, load_tasks, validate_dataset
from .manifest import RunManifest, audit_comparability, file_sha256
from .receipts import canonical_sha256, seal_receipt, verify_receipt
from .runner import BenchmarkRunner, ReplayAdapter
from .schema import Decision, Family, Prediction, Task
from .scoring import AggregateMetrics, TaskScore, aggregate_scores, score_prediction
from .systems import SYSTEM_CONTRACTS, get_system_contract, validate_prediction_contract

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
    "RunManifest",
    "SYSTEM_CONTRACTS",
    "audit_comparability",
    "capture_predictions",
    "dataset_sha256",
    "file_sha256",
    "get_system_contract",
    "validate_prediction_contract",
]
