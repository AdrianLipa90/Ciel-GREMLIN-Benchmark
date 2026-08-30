from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Mapping

from .manifest import RunManifest, audit_comparability, load_manifest
from .scoring import AggregateMetrics


@dataclass(frozen=True)
class ExperimentComparison:
    systems: tuple[str, ...]
    metrics: Mapping[str, AggregateMetrics]
    relative_eer_reduction_vs_b1: Mapping[str, float | None]
    relative_ceer_reduction_vs_b1: Mapping[str, float | None]

    def to_dict(self) -> dict:
        return {
            "schema": "CIEL_GREMLIN_EXPERIMENT_COMPARISON_V0_1",
            "systems": list(self.systems),
            "metrics": {key: asdict(value) for key, value in self.metrics.items()},
            "relative_eer_reduction_vs_b1": dict(self.relative_eer_reduction_vs_b1),
            "relative_ceer_reduction_vs_b1": dict(self.relative_ceer_reduction_vs_b1),
        }


def _load_metrics(path: str | Path) -> AggregateMetrics:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    metrics = dict(raw["metrics"])
    return AggregateMetrics(**metrics)


def _relative_reduction(baseline: float, value: float) -> float | None:
    if baseline <= 0:
        return None
    return (baseline - value) / baseline


def compare_runs(run_dirs: list[str | Path]) -> ExperimentComparison:
    manifests: list[RunManifest] = []
    metrics_by_system: dict[str, AggregateMetrics] = {}
    for raw_dir in run_dirs:
        run_dir = Path(raw_dir)
        manifest = load_manifest(run_dir / "manifest.json")
        metrics = _load_metrics(run_dir / "result.json")
        if metrics.system_id != manifest.system_id:
            raise ValueError(
                f"{run_dir}: result system_id={metrics.system_id!r} does not match manifest {manifest.system_id!r}"
            )
        manifests.append(manifest)
        metrics_by_system[manifest.system_id] = metrics

    issues = audit_comparability(manifests)
    if issues:
        raise ValueError("experiment comparability audit failed: " + "; ".join(issues))
    if "B1" not in metrics_by_system:
        raise ValueError("comparison requires B1 structured baseline")

    b1 = metrics_by_system["B1"]
    eer_reduction = {
        system_id: _relative_reduction(b1.execution_error_rate, metrics.execution_error_rate)
        for system_id, metrics in metrics_by_system.items()
    }
    ceer_reduction = {
        system_id: _relative_reduction(
            b1.catastrophic_execution_error_rate,
            metrics.catastrophic_execution_error_rate,
        )
        for system_id, metrics in metrics_by_system.items()
    }
    return ExperimentComparison(
        systems=tuple(sorted(metrics_by_system)),
        metrics=dict(sorted(metrics_by_system.items())),
        relative_eer_reduction_vs_b1=eer_reduction,
        relative_ceer_reduction_vs_b1=ceer_reduction,
    )
