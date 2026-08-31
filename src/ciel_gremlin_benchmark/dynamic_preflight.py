from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Any, Mapping

from .dataset import dataset_sha256, load_tasks
from .dynamic_gate import validate_ciel_receipt
from .manifest import audit_comparability, file_sha256, load_manifest


SYSTEM_IDS = ("B0", "B1", "B2", "B3", "B4")


@dataclass(frozen=True)
class DynamicLivePreflightReport:
    status: str
    dataset_sha256: str | None
    task_count: int
    systems: tuple[str, ...]
    issues: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _receipt_rows(path: Path) -> dict[str, Mapping[str, Any]]:
    rows: dict[str, Mapping[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            raw = json.loads(line)
            if not isinstance(raw, Mapping):
                raise ValueError(f"{path}:{line_no}: receipt row must be object")
            task_id = str(raw.get("task_id") or "")
            if not task_id:
                raise ValueError(f"{path}:{line_no}: missing task_id")
            if task_id in rows:
                raise ValueError(f"{path}:{line_no}: duplicate task_id={task_id!r}")
            rows[task_id] = raw
    return rows


def _check_bundle(
    system_id: str,
    path: Path,
    task_ids: set[str],
    issues: list[str],
) -> None:
    try:
        rows = _receipt_rows(path)
    except Exception as exc:
        issues.append(f"{system_id}: invalid receipt bundle: {exc}")
        return

    missing = sorted(task_ids - set(rows))
    extra = sorted(set(rows) - task_ids)
    if missing:
        issues.append(f"{system_id}: receipt coverage missing {len(missing)} task(s)")
    if extra:
        issues.append(f"{system_id}: receipt bundle has {len(extra)} unknown task(s)")

    for task_id in sorted(task_ids & set(rows)):
        row = rows[task_id]
        if row.get("execution_gate") not in (None, {}, [], ""):
            issues.append(f"{system_id}:{task_id}: precomputed execution_gate is forbidden")

        gremlin = row.get("gremlin")
        ciel = row.get("ciel")
        if system_id == "B2":
            if not isinstance(gremlin, Mapping):
                issues.append(f"{system_id}:{task_id}: missing GREMLIN receipt")
            if ciel not in (None, {}, [], ""):
                issues.append(f"{system_id}:{task_id}: CIEL receipt contaminates GREMLIN-only ablation")
        elif system_id == "B3":
            if gremlin not in (None, {}, [], ""):
                issues.append(f"{system_id}:{task_id}: GREMLIN receipt contaminates CIEL-only ablation")
            if not isinstance(ciel, Mapping):
                issues.append(f"{system_id}:{task_id}: missing CIEL receipt")
            else:
                for issue in validate_ciel_receipt(ciel):
                    issues.append(f"{system_id}:{task_id}: {issue}")
        elif system_id == "B4":
            if not isinstance(gremlin, Mapping):
                issues.append(f"{system_id}:{task_id}: missing GREMLIN receipt")
            if not isinstance(ciel, Mapping):
                issues.append(f"{system_id}:{task_id}: missing CIEL receipt")
            else:
                for issue in validate_ciel_receipt(ciel):
                    issues.append(f"{system_id}:{task_id}: {issue}")


def dynamic_preflight_live(
    *,
    dataset: str | Path,
    run_root: str | Path,
    prompt_paths: Mapping[str, str | Path],
    receipt_paths: Mapping[str, str | Path],
    api_key_env: str = "OPENAI_API_KEY",
    require_api_key: bool = True,
) -> DynamicLivePreflightReport:
    issues: list[str] = []
    warnings: list[str] = []
    dataset_path = Path(dataset)
    root = Path(run_root)

    try:
        tasks = load_tasks(dataset_path)
        digest = dataset_sha256(dataset_path)
    except Exception as exc:
        return DynamicLivePreflightReport(
            status="FAIL",
            dataset_sha256=None,
            task_count=0,
            systems=(),
            issues=(f"dataset invalid: {exc}",),
            warnings=(),
        )
    task_ids = {task.task_id for task in tasks}

    manifests = []
    by_system = {}
    for system_id in SYSTEM_IDS:
        path = root / system_id / "manifest.json"
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
        manifest = by_system.get(system_id)
        if manifest is None:
            continue
        path = Path(prompt_path)
        if not path.exists():
            issues.append(f"{system_id}: missing prompt {path}")
        elif file_sha256(path) != manifest.prompt_sha256:
            issues.append(f"{system_id}: prompt bytes differ from manifest")

    for system_id in ("B2", "B3", "B4"):
        raw_path = receipt_paths.get(system_id)
        if not raw_path:
            issues.append(f"{system_id}: receipt bundle path not supplied")
            continue
        path = Path(raw_path)
        if not path.exists():
            issues.append(f"{system_id}: receipt bundle missing: {path}")
            continue
        _check_bundle(system_id, path, task_ids, issues)

    key = os.environ.get(api_key_env, "").strip()
    if require_api_key and not key:
        issues.append(f"API credential missing: environment variable {api_key_env}")
    elif not require_api_key and not key:
        warnings.append(f"API credential absent: {api_key_env}; network capture remains blocked")

    return DynamicLivePreflightReport(
        status="FAIL" if issues else "PASS",
        dataset_sha256=digest,
        task_count=len(tasks),
        systems=tuple(sorted(by_system)),
        issues=tuple(issues),
        warnings=tuple(warnings),
    )


__all__ = ["DynamicLivePreflightReport", "dynamic_preflight_live"]
