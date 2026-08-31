from pathlib import Path

import pytest

from ciel_gremlin_benchmark.capture import capture_predictions
from ciel_gremlin_benchmark.runner import ReplayAdapter
from ciel_gremlin_benchmark.schema import Decision, Family, GroundTruth, Prediction, Task


def task() -> Task:
    return Task(
        task_id="T1",
        family=Family.F1_ENTITY_RECIPIENT,
        language="en",
        user_input="Send the report to Zosia.",
        world_state={},
        evidence=(),
        allowed_tools=("send_email",),
        ground_truth=GroundTruth(
            decision=Decision.EXECUTE,
            tool="send_email",
            arguments={"recipient": "Zosia", "document": "report"},
        ),
    )


def test_capture_is_atomic_replay_input(tmp_path: Path):
    prediction = Prediction(
        system_id="B1",
        task_id="T1",
        decision=Decision.EXECUTE,
        tool="send_email",
        arguments={"recipient": "Zosia", "document": "report"},
        receipts={"structured_output": {"schema": "tool_call"}},
    )
    out = tmp_path / "b1.jsonl"
    capture_predictions([task()], ReplayAdapter("B1", {"T1": prediction}), out)
    replay = ReplayAdapter.from_jsonl(out, "B1")
    assert replay.predict(task()).arguments["recipient"] == "Zosia"


def test_capture_rejects_b4_without_required_receipts(tmp_path: Path):
    prediction = Prediction(system_id="B4", task_id="T1", decision=Decision.DEFER)
    with pytest.raises(ValueError, match="system|receipt|invalid captured"):
        capture_predictions(
            [task()],
            ReplayAdapter("B4", {"T1": prediction}),
            tmp_path / "b4.jsonl",
        )
