from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .schema import Task


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def evidence_rows_for_task(task: Task) -> list[dict[str, Any]]:
    """Map benchmark evidence to GREMLIN source rows without ground-truth access."""
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(task.evidence):
        raw = dict(item)
        label = str(raw.get("claim") or raw.get("source") or raw.get("status") or f"row-{index}")
        source = str(raw.get("source") or "task")
        rows.append({
            "provider": f"benchmark:{source}",
            "title": f"Benchmark evidence {index + 1}: {label}",
            "url": f"benchmark://{task.task_id}/evidence/{index}",
            "summary": _canonical_json(raw),
            "published": raw.get("published"),
        })
    return rows


def build_gremlin_receipt_rows(
    tasks: Iterable[Task],
    executor: Callable[..., Mapping[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for task in tasks:
        result = executor(
            task.user_input,
            evidence_rows_for_task(task),
            relation_text=task.user_input,
            language=task.language,
        )
        if not isinstance(result, Mapping):
            raise ValueError(f"{task.task_id}: GREMLIN executor returned non-object")
        receipt = dict(result)
        authority = receipt.get("authority")
        if not isinstance(authority, Mapping):
            raise ValueError(f"{task.task_id}: GREMLIN receipt lacks authority object")
        if any(bool(authority.get(key)) for key in ("production_runtime_write", "execution_admitted", "canon_allowed")):
            raise ValueError(f"{task.task_id}: GREMLIN receipt exceeds candidate-only authority")
        out.append({"task_id": task.task_id, "gremlin": receipt})
    return out


def write_gremlin_receipt_bundle(
    tasks: Iterable[Task],
    executor: Callable[..., Mapping[str, Any]],
    output_path: str | Path,
) -> dict[str, Any]:
    rows = build_gremlin_receipt_rows(tasks, executor)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(_canonical_json(row) + "\n")
    tmp.replace(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "schema": "CIEL_GREMLIN_GREMLIN_RECEIPT_BUNDLE_V0_1",
        "task_count": len(rows),
        "sha256": digest,
        "output": str(path),
    }


def native_gremlin_executor() -> Callable[..., Mapping[str, Any]]:
    try:
        from gremlin_mcp.supplied_evidence import execute_supplied_evidence_research
    except ImportError as exc:
        raise RuntimeError("GREMLIN supplied-evidence lane is not installed") from exc
    return execute_supplied_evidence_research


__all__ = [
    "build_gremlin_receipt_rows",
    "evidence_rows_for_task",
    "native_gremlin_executor",
    "write_gremlin_receipt_bundle",
]
