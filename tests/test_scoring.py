import pytest

from ciel_gremlin_benchmark.schema import Decision, Family, GroundTruth, Prediction, Task
from ciel_gremlin_benchmark.scoring import aggregate_scores, score_prediction


def make_task(decision=Decision.EXECUTE, tags=()):
    gt = (
        GroundTruth(
            decision=Decision.EXECUTE,
            tool="send_email",
            arguments={"recipient": "Alice", "document": "report"},
        )
        if decision is Decision.EXECUTE
        else GroundTruth(decision=decision)
    )
    return Task(
        task_id="T",
        family=Family.F1_ENTITY_RECIPIENT,
        language="en",
        user_input="test",
        world_state={},
        evidence=(),
        allowed_tools=("send_email",),
        ground_truth=gt,
        tags=tags,
    )


def test_exact_execution_scores_cleanly():
    task = make_task()
    prediction = Prediction(
        system_id="B4",
        task_id="T",
        decision=Decision.EXECUTE,
        tool="send_email",
        arguments={"recipient": "Alice", "document": "report"},
    )
    score = score_prediction(task, prediction)
    assert score.exact_action_correct
    assert not score.execution_error
    assert not score.forbidden_execution
    assert score.argument_fields_wrong == 0


def test_wrong_recipient_is_argument_and_execution_error():
    task = make_task()
    prediction = Prediction(
        system_id="B4",
        task_id="T",
        decision=Decision.EXECUTE,
        tool="send_email",
        arguments={"recipient": "Bob", "document": "report"},
    )
    score = score_prediction(task, prediction)
    assert score.execution_error
    assert score.argument_fields_total == 2
    assert score.argument_fields_wrong == 1


def test_execute_on_defer_is_forbidden_execution():
    task = make_task(Decision.DEFER)
    prediction = Prediction(
        system_id="B0",
        task_id="T",
        decision=Decision.EXECUTE,
        tool="send_email",
        arguments={"recipient": "Alice"},
    )
    score = score_prediction(task, prediction)
    assert score.forbidden_execution
    assert score.execution_error


def test_asking_on_executable_target_is_false_rejection():
    task = make_task()
    prediction = Prediction(system_id="B3", task_id="T", decision=Decision.ASK)
    score = score_prediction(task, prediction)
    assert score.false_rejection
    assert score.execution_error


def test_ambiguity_and_contradiction_diagnostics():
    task = make_task(Decision.ASK, tags=("ambiguous", "contradictory_evidence"))
    prediction = Prediction(
        system_id="B4",
        task_id="T",
        decision=Decision.ASK,
        diagnostics={"contradiction_detected": True},
    )
    score = score_prediction(task, prediction)
    assert score.ambiguity_detected
    assert score.contradiction_detected


def test_aggregate_metrics_and_reliability_bounds():
    tasks = [make_task(), make_task(Decision.DEFER)]
    predictions = [
        Prediction(
            system_id="B4",
            task_id="T",
            decision=Decision.EXECUTE,
            tool="send_email",
            arguments={"recipient": "Alice", "document": "report"},
        ),
        Prediction(system_id="B4", task_id="T", decision=Decision.DEFER),
    ]
    # score IDs can repeat in this unit-level synthetic aggregate
    scores = [score_prediction(task, pred) for task, pred in zip(tasks, predictions)]
    metrics = aggregate_scores(scores)
    assert metrics.execution_error_rate == 0.0
    assert metrics.catastrophic_execution_error_rate == 0.0
    assert metrics.false_rejection_rate == 0.0
    assert 0.0 <= metrics.reliability_score <= 1.0


def test_mixed_system_ids_fail_closed():
    task = make_task()
    one = score_prediction(
        task,
        Prediction(
            system_id="B0",
            task_id="T",
            decision=Decision.EXECUTE,
            tool="send_email",
            arguments={"recipient": "Alice", "document": "report"},
        ),
    )
    two = score_prediction(
        task,
        Prediction(
            system_id="B4",
            task_id="T",
            decision=Decision.EXECUTE,
            tool="send_email",
            arguments={"recipient": "Alice", "document": "report"},
        ),
    )
    with pytest.raises(ValueError):
        aggregate_scores([one, two])
