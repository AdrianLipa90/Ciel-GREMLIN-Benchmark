import pytest
import json
from dataclasses import asdict
from pathlib import Path

from ciel_gremlin_benchmark.experiment import compare_runs
from ciel_gremlin_benchmark.manifest import RunManifest
from ciel_gremlin_benchmark.scoring import AggregateMetrics


D = "d" * 64
C = "c" * 40


def _write_run(root: Path, system_id: str, eer: float, ceer: float, components=None):
    root.mkdir()
    manifest = RunManifest(
        run_id=f"run-{system_id}",
        system_id=system_id,
        dataset_sha256=D,
        benchmark_commit=C,
        model_provider="provider",
        model_id="model-x",
        model_parameters={"temperature": 0},
        prompt_sha256=("1" if system_id == "B1" else "2") * 64,
        component_commits=components or {},
    )
    (root / "manifest.json").write_text(json.dumps(manifest.to_dict()), encoding="utf-8")
    metrics = AggregateMetrics(
        system_id=system_id,
        tasks=60,
        decision_accuracy=0.8,
        exact_action_accuracy=1.0 - eer,
        execution_error_rate=eer,
        catastrophic_execution_error_rate=ceer,
        argument_error_rate=0.1,
        false_rejection_rate=0.1,
        ambiguity_detection_recall=0.9,
        contradiction_detection_recall=0.9,
        evidence_grounded_execution_rate=0.9,
        reliability_score=0.8,
    )
    (root / "result.json").write_text(
        json.dumps({"metrics": asdict(metrics)}), encoding="utf-8"
    )


def test_compare_runs_reports_relative_reduction_vs_b1(tmp_path: Path):
    b1 = tmp_path / "b1"
    b4 = tmp_path / "b4"
    _write_run(b1, "B1", 0.20, 0.10)
    _write_run(
        b4,
        "B4",
        0.10,
        0.02,
        {"gremlin": "a" * 40, "cielingo": "b" * 40, "ciel_semantic": "e" * 40},
    )
    comparison = compare_runs([b1, b4])
    assert comparison.relative_eer_reduction_vs_b1["B4"] == 0.5
    assert comparison.relative_ceer_reduction_vs_b1["B4"] == pytest.approx(0.8)
