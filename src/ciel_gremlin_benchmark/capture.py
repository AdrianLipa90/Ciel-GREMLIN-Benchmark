from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Iterable

from .runner import SystemAdapter
from .schema import Prediction, Task
from .systems import get_system_contract, validate_prediction_contract


def prediction_to_dict(prediction: Prediction) -> dict:
    return {
        "system_id": prediction.system_id,
        "task_id": prediction.task_id,
        "decision": prediction.decision.value,
        "tool": prediction.tool,
        "arguments": dict(prediction.arguments),
        "diagnostics": dict(prediction.diagnostics),
        "receipts": dict(prediction.receipts),
        "cost": asdict(prediction.cost),
    }


def capture_predictions(
    tasks: Iterable[Task],
    adapter: SystemAdapter,
    output_path: str | Path,
    *,
    strict_system_contract: bool = True,
) -> list[Prediction]:
    """Invoke an adapter once per task and atomically capture raw predictions.

    Capture performs schema/provenance validation only. It never scores or repairs
    a prediction. The resulting JSONL is the immutable replay input for scoring.
    """
    contract = get_system_contract(adapter.system_id)
    tasks = list(tasks)
    predictions: list[Prediction] = []
    seen: set[str] = set()

    for task in tasks:
        prediction = adapter.predict(task)
        if prediction.system_id != contract.system_id:
            raise ValueError(
                f"{task.task_id}: adapter system_id={contract.system_id!r} emitted "
                f"prediction system_id={prediction.system_id!r}"
            )
        if prediction.task_id != task.task_id:
            raise ValueError(
                f"{task.task_id}: adapter emitted prediction for {prediction.task_id!r}"
            )
        if prediction.task_id in seen:
            raise ValueError(f"duplicate captured prediction {prediction.task_id!r}")
        seen.add(prediction.task_id)
        issues = prediction.validate()
        if strict_system_contract:
            issues.extend(validate_prediction_contract(prediction))
        if issues:
            raise ValueError(
                f"{task.task_id}: invalid captured prediction: " + "; ".join(issues)
            )
        predictions.append(prediction)

    if len(predictions) != len(tasks):
        raise ValueError("capture coverage mismatch")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for prediction in predictions:
            handle.write(json.dumps(
                prediction_to_dict(prediction),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ))
            handle.write("\n")
    tmp.replace(path)
    return predictions
