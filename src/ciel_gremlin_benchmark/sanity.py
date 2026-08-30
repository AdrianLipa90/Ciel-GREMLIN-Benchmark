from __future__ import annotations

from .schema import Decision, Prediction, Task
from .scoring import AggregateMetrics
from .runner import BenchmarkRunner, ReplayAdapter


def _oracle(task: Task, system_id: str) -> Prediction:
    gt = task.ground_truth
    diagnostics = {}
    if "contradictory_evidence" in task.tags:
        diagnostics["contradiction_detected"] = True
    if "evidence_dependent" in task.tags and gt.decision is Decision.EXECUTE:
        diagnostics["evidence_sufficient"] = True
    return Prediction(
        system_id=system_id,
        task_id=task.task_id,
        decision=gt.decision,
        tool=gt.tool,
        arguments=dict(gt.arguments),
        diagnostics=diagnostics,
    )


def _always_defer(task: Task, system_id: str) -> Prediction:
    return Prediction(system_id=system_id, task_id=task.task_id, decision=Decision.DEFER)


def _reckless_execute(task: Task, system_id: str) -> Prediction:
    tool = task.allowed_tools[0] if task.allowed_tools else "unavailable_tool"
    return Prediction(
        system_id=system_id,
        task_id=task.task_id,
        decision=Decision.EXECUTE,
        tool=tool,
        arguments={"guessed": True},
    )


def run_metric_sanity(tasks: list[Task]) -> dict[str, AggregateMetrics]:
    systems = {
        "SANITY_ORACLE": {_task.task_id: _oracle(_task, "SANITY_ORACLE") for _task in tasks},
        "SANITY_DEFER": {_task.task_id: _always_defer(_task, "SANITY_DEFER") for _task in tasks},
        "SANITY_RECKLESS": {_task.task_id: _reckless_execute(_task, "SANITY_RECKLESS") for _task in tasks},
    }
    runner = BenchmarkRunner()
    out: dict[str, AggregateMetrics] = {}
    for system_id, predictions in systems.items():
        _, metrics = runner.run(tasks, ReplayAdapter(system_id, predictions))
        out[system_id] = metrics
    return out
