from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .manifest import file_sha256
from .schema import Family, Task


def load_tasks(path: str | Path) -> list[Task]:
    path = Path(path)
    tasks: list[Task] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            try:
                tasks.append(Task.from_dict(raw))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"{path}:{line_no}: invalid task: {exc}") from exc
    validate_dataset(tasks)
    return tasks


def validate_dataset(tasks: Iterable[Task]) -> None:
    tasks = list(tasks)
    if not tasks:
        raise ValueError("dataset is empty")

    seen: set[str] = set()
    errors: list[str] = []
    family_counts = {family: 0 for family in Family}

    for task in tasks:
        if task.task_id in seen:
            errors.append(f"{task.task_id}: duplicate task_id")
        seen.add(task.task_id)
        family_counts[task.family] += 1
        errors.extend(f"{task.task_id}: {issue}" for issue in task.validate())

    if errors:
        raise ValueError("dataset validation failed:\n" + "\n".join(errors))


def family_counts(tasks: Iterable[Task]) -> dict[str, int]:
    counts = {family.value: 0 for family in Family}
    for task in tasks:
        counts[task.family.value] += 1
    return counts


def dataset_sha256(path: str | Path) -> str:
    """SHA-256 of the exact dataset bytes used for a run manifest."""
    return file_sha256(path)
