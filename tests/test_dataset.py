from collections import Counter
from pathlib import Path

from ciel_gremlin_benchmark.dataset import load_tasks
from ciel_gremlin_benchmark.schema import Family


DATASET = Path(__file__).parents[1] / "dataset" / "golden_v0_1.jsonl"


def test_golden_dataset_has_60_tasks_and_10_per_family():
    tasks = load_tasks(DATASET)
    assert len(tasks) == 60
    counts = Counter(task.family for task in tasks)
    assert set(counts) == set(Family)
    assert all(counts[family] == 10 for family in Family)


def test_ids_are_unique_and_ground_truth_is_valid():
    tasks = load_tasks(DATASET)
    ids = [task.task_id for task in tasks]
    assert len(ids) == len(set(ids))
    assert all(task.validate() == [] for task in tasks)


def test_cross_language_groups_are_paired():
    tasks = load_tasks(DATASET)
    groups = {}
    for task in tasks:
        group = task.metadata.get("semantic_group")
        if group:
            groups.setdefault(group, []).append(task)
    assert len(groups) == 5
    for pair in groups.values():
        assert len(pair) == 2
        assert {task.language for task in pair} == {"pl", "en"}
        assert pair[0].ground_truth.decision == pair[1].ground_truth.decision
        assert pair[0].ground_truth.tool == pair[1].ground_truth.tool
        assert dict(pair[0].ground_truth.arguments) == dict(pair[1].ground_truth.arguments)
