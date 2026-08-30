from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Mapping, Protocol

from .sandbox import ExecutionSandbox
from .schema import Prediction, Task
from .scoring import AggregateMetrics, aggregate_scores, score_prediction


class SystemAdapter(Protocol):
    system_id: str

    def predict(self, task: Task) -> Prediction:
        ...


class ReplayAdapter:
    """Adapter for deterministic replay of previously captured predictions."""

    def __init__(self, system_id: str, predictions: Mapping[str, Prediction]):
        self.system_id = system_id
        self._predictions = dict(predictions)

    @classmethod
    def from_jsonl(cls, path: str | Path, system_id: str) -> "ReplayAdapter":
        predictions: dict[str, Prediction] = {}
        with Path(path).open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                raw = json.loads(line)
                prediction = Prediction.from_dict(raw)
                if prediction.system_id != system_id:
                    raise ValueError(
                        f"{path}:{line_no}: expected system_id={system_id!r}, "
                        f"got {prediction.system_id!r}"
                    )
                if prediction.task_id in predictions:
                    raise ValueError(
                        f"{path}:{line_no}: duplicate task_id={prediction.task_id!r}"
                    )
                predictions[prediction.task_id] = prediction
        return cls(system_id, predictions)

    def predict(self, task: Task) -> Prediction:
        try:
            return self._predictions[task.task_id]
        except KeyError as exc:
            raise KeyError(
                f"missing replay prediction for {task.task_id!r}"
            ) from exc


class BenchmarkRunner:
    def __init__(self, sandbox: ExecutionSandbox | None = None):
        self.sandbox = sandbox or ExecutionSandbox()

    def run(self, tasks: list[Task], adapter: SystemAdapter) -> tuple[list[dict], AggregateMetrics]:
        records: list[dict] = []
        scores = []

        for task in tasks:
            prediction = adapter.predict(task)
            issues = prediction.validate()
            if issues:
                raise ValueError(
                    f"{task.task_id}: invalid prediction: " + "; ".join(issues)
                )

            sandbox_record = self.sandbox.execute(task, prediction)
            score = score_prediction(task, prediction)
            scores.append(score)
            records.append(
                {
                    "task_id": task.task_id,
                    "system_id": adapter.system_id,
                    "prediction": {
                        "decision": prediction.decision.value,
                        "tool": prediction.tool,
                        "arguments": dict(prediction.arguments),
                        "diagnostics": dict(prediction.diagnostics),
                        "receipts": dict(prediction.receipts),
                        "cost": asdict(prediction.cost),
                    },
                    "sandbox": asdict(sandbox_record) if sandbox_record else None,
                    "score": asdict(score),
                }
            )

        return records, aggregate_scores(scores)
