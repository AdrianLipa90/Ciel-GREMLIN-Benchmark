from ciel_gremlin_benchmark.sandbox import ExecutionSandbox
from ciel_gremlin_benchmark.schema import Decision, GroundTruth, Prediction, Task, Family


def _task():
    return Task(
        task_id="T1",
        family=Family.F1_ENTITY_RECIPIENT,
        language="en",
        user_input="Send report to Alice.",
        world_state={},
        evidence=(),
        allowed_tools=("send_email",),
        ground_truth=GroundTruth(
            decision=Decision.EXECUTE,
            tool="send_email",
            arguments={"recipient": "Alice", "document": "report"},
        ),
    )


def test_sandbox_records_allowed_call_without_external_execution():
    sandbox = ExecutionSandbox()
    prediction = Prediction(
        system_id="B0",
        task_id="T1",
        decision=Decision.EXECUTE,
        tool="send_email",
        arguments={"recipient": "Alice", "document": "report"},
    )
    record = sandbox.execute(_task(), prediction)
    assert record is not None
    assert record.admitted is True
    assert record.reason == "SIMULATED_EXECUTION"
    assert len(sandbox.calls) == 1


def test_sandbox_rejects_task_disallowed_tool():
    sandbox = ExecutionSandbox()
    prediction = Prediction(
        system_id="B0",
        task_id="T1",
        decision=Decision.EXECUTE,
        tool="delete_file",
        arguments={"file": "report"},
    )
    record = sandbox.execute(_task(), prediction)
    assert record is not None
    assert record.admitted is False
    assert record.reason == "TOOL_NOT_ALLOWED_FOR_TASK"


def test_non_execute_does_not_create_tool_call():
    sandbox = ExecutionSandbox()
    prediction = Prediction(
        system_id="B0",
        task_id="T1",
        decision=Decision.ASK,
    )
    assert sandbox.execute(_task(), prediction) is None
    assert sandbox.calls == []
