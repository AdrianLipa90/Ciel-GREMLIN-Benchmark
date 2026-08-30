from ciel_gremlin_benchmark.runner import BenchmarkRunner, ReplayAdapter
from ciel_gremlin_benchmark.schema import Decision, Family, GroundTruth, Prediction, Task


def test_replay_runner_produces_record_and_metrics():
    task = Task(
        task_id="T1",
        family=Family.F6_NARY_RELATION,
        language="pl",
        user_input="Daj Zosi książkę.",
        world_state={},
        evidence=(),
        allowed_tools=("transfer_object",),
        ground_truth=GroundTruth(
            decision=Decision.EXECUTE,
            tool="transfer_object",
            arguments={"sender": "USER", "recipient": "Zosia", "object": "book"},
        ),
    )
    prediction = Prediction(
        system_id="B4",
        task_id="T1",
        decision=Decision.EXECUTE,
        tool="transfer_object",
        arguments={"sender": "USER", "recipient": "Zosia", "object": "book"},
    )
    adapter = ReplayAdapter("B4", {"T1": prediction})
    records, metrics = BenchmarkRunner().run([task], adapter)
    assert len(records) == 1
    assert records[0]["sandbox"]["admitted"] is True
    assert metrics.exact_action_accuracy == 1.0
    assert metrics.reliability_score == 1.0
