from __future__ import annotations

import json
from pathlib import Path

from ciel_gremlin_benchmark.dataset import load_tasks
from ciel_gremlin_benchmark.gremlin_receipts import (
    build_gremlin_receipt_rows,
    evidence_rows_for_task,
    write_gremlin_receipt_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset" / "golden_v0_1.jsonl"


def _executor(query, evidence_rows, *, relation_text, language):
    return {
        "schema": "GREMLIN_TEST",
        "query": query,
        "evidence_rows": evidence_rows,
        "relation_text": relation_text,
        "language": language,
        "authority": {
            "production_runtime_write": False,
            "execution_admitted": False,
            "canon_allowed": False,
        },
    }


def test_evidence_mapping_exposes_only_task_evidence() -> None:
    task = next(task for task in load_tasks(DATASET) if task.task_id == "F4-001")
    rows = evidence_rows_for_task(task)
    assert len(rows) == 1
    assert rows[0]["provider"] == "benchmark:registry"
    decoded = json.loads(rows[0]["summary"])
    assert decoded == dict(task.evidence[0])
    assert "ground_truth" not in rows[0]["summary"]
    assert "approve_supplier" not in rows[0]["summary"]


def test_all_tasks_receive_candidate_only_gremlin_receipt() -> None:
    tasks = load_tasks(DATASET)
    rows = build_gremlin_receipt_rows(tasks, _executor)
    assert len(rows) == 60
    assert len({row["task_id"] for row in rows}) == 60
    assert all(row["gremlin"]["authority"]["execution_admitted"] is False for row in rows)


def test_bundle_is_deterministic(tmp_path: Path) -> None:
    tasks = load_tasks(DATASET)
    first = write_gremlin_receipt_bundle(tasks, _executor, tmp_path / "a.jsonl")
    second = write_gremlin_receipt_bundle(tasks, _executor, tmp_path / "b.jsonl")
    assert first["task_count"] == second["task_count"] == 60
    assert first["sha256"] == second["sha256"]
    assert (tmp_path / "a.jsonl").read_bytes() == (tmp_path / "b.jsonl").read_bytes()


def test_authority_escalation_is_rejected() -> None:
    task = load_tasks(DATASET)[0]
    def bad(*args, **kwargs):
        return {"authority": {"production_runtime_write": False, "execution_admitted": True, "canon_allowed": False}}
    try:
        build_gremlin_receipt_rows([task], bad)
    except ValueError as exc:
        assert "exceeds candidate-only authority" in str(exc)
    else:
        raise AssertionError("authority escalation was accepted")
