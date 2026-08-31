from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import os
from pathlib import Path
from typing import Mapping

from .dataset import dataset_sha256, load_tasks
from .manifest import audit_comparability, file_sha256, load_manifest
from .systems import get_system_contract


SYSTEM_IDS = ("B0", "B1", "B2", "B3", "B4")


@dataclass(frozen=True)
class LivePreflightReport:
    status: str
    dataset_sha256: str | None
    task_count: int
    systems: tuple[str, ...]
    issues: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _receipt_rows(path: Path) -> dict[str, Mapping]:
    rows: dict[str, Mapping] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            raw = json.loads(line)
            if not isinstance(raw, Mapping):
                raise ValueError(f"{path}:{line_no}: receipt row must be object")
            task_id = str(raw.get("task_id", ""))
            if not task_id:
                raise ValueError(f"{path}:{line_no}: missing task_id")
            if task_id in rows:
                raise ValueError(f"{path}:{line_no}: duplicate task_id={task_id!r}")
            rows[task_id] = raw
    return rows


def preflight_live(
    *,
    dataset: str | Path,
    run_root: str | Path,
    prompt_paths: Mapping[str, str | Path],
    receipt_paths: Mapping[str, str | Path] | None = None,
    api_key_env: str = "OPENAI_API_KEY",
    require_api_key: bool = True,
) -> LivePreflightReport:
    issues: list[str] = []
    warnings: list[str] = []
    dataset_path = Path(dataset)
    run_root = Path(run_root)
    receipt_paths = dict(receipt_paths or {})

    try:
        tasks = load_tasks(dataset_path)
        digest = dataset_sha256(dataset_path)
    except Exception as exc:
        return LivePreflightReport(
            status="FAIL", dataset_sha256=None, task_count=0, systems=(),
            issues=(f"dataset invalid: {exc}",), warnings=(),
        )
    task_ids = {task.task_id for task in tasks}

    manifests = []
    by_system = {}
    for system_id in SYSTEM_IDS:
        path = run_root / system_id / "manifest.json"
        if not path.exists():
            issues.append(f"{system_id}: missing manifest {path}")
            continue
        try:
            manifest = load_manifest(path)
        except Exception as exc:
            issues.append(f"{system_id}: invalid manifest: {exc}")
            continue
        manifests.append(manifest)
        by_system[system_id] = manifest
        if manifest.system_id != system_id:
            issues.append(f"{system_id}: manifest system_id={manifest.system_id!r}")
        if manifest.dataset_sha256 != digest:
            issues.append(f"{system_id}: dataset fingerprint mismatch")

    if len(manifests) == len(SYSTEM_IDS):
        issues.extend(audit_comparability(manifests))

    for system_id, prompt_path in prompt_paths.items():
        if system_id not in by_system:
            continue
        path = Path(prompt_path)
        if not path.exists():
            issues.append(f"{system_id}: missing prompt {path}")
            continue
        if file_sha256(path) != by_system[system_id].prompt_sha256:
            issues.append(f"{system_id}: prompt bytes differ from manifest")

    for system_id in ("B2", "B3", "B4"):
        contract = get_system_contract(system_id)
        path_raw = receipt_paths.get(system_id)
        if not path_raw:
            issues.append(f"{system_id}: receipt bundle path not supplied")
            continue
        path = Path(path_raw)
        if not path.exists():
            issues.append(f"{system_id}: receipt bundle missing: {path}")
            continue
        try:
            rows = _receipt_rows(path)
        except Exception as exc:
            issues.append(f"{system_id}: invalid receipt bundle: {exc}")
            continue
        missing = sorted(task_ids - set(rows))
        extra = sorted(set(rows) - task_ids)
        if missing:
            issues.append(f"{system_id}: receipt coverage missing {len(missing)} task(s)")
        if extra:
            issues.append(f"{system_id}: receipt bundle has {len(extra)} unknown task(s)")
        required = tuple(name for name in contract.required_receipts if name != "structured_output")
        for task_id in sorted(task_ids & set(rows)):
            row = rows[task_id]
            for name in required:
                if row.get(name) in (None, {}, [], ""):
                    issues.append(f"{system_id}:{task_id}: missing receipt {name!r}")

    if require_api_key and not os.environ.get(api_key_env, "").strip():
        issues.append(f"API credential missing: environment variable {api_key_env}")
    elif not require_api_key and not os.environ.get(api_key_env, "").strip():
        warnings.append(f"API credential absent: {api_key_env}; network capture remains blocked")

    return LivePreflightReport(
        status="FAIL" if issues else "PASS",
        dataset_sha256=digest,
        task_count=len(tasks),
        systems=tuple(sorted(by_system)),
        issues=tuple(issues),
        warnings=tuple(warnings),
    )
