from __future__ import annotations

import json
from pathlib import Path

from ciel_gremlin_benchmark.dataset import dataset_sha256, load_tasks
from ciel_gremlin_benchmark.manifest import RunManifest, file_sha256
from ciel_gremlin_benchmark.preflight import preflight_live


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset" / "golden_v0_1.jsonl"
P0 = ROOT / "prompts" / "b0_direct.txt"
P13 = ROOT / "prompts" / "b1_b3_structured.txt"
P24 = ROOT / "prompts" / "b2_b4_research_structured.txt"
BENCH = "8" * 40
G = "a" * 40
CI = "b" * 40
CS = "c" * 40


def _make_run_root(tmp_path: Path) -> Path:
    run_root = tmp_path / "run"
    prompts = {"B0": P0, "B1": P13, "B2": P24, "B3": P13, "B4": P24}
    components = {
        "B0": {},
        "B1": {},
        "B2": {"gremlin": G},
        "B3": {"cielingo": CI, "ciel_semantic": CS},
        "B4": {"gremlin": G, "cielingo": CI, "ciel_semantic": CS},
    }
    for system_id in prompts:
        manifest = RunManifest(
            run_id=f"r-{system_id}", system_id=system_id,
            dataset_sha256=dataset_sha256(DATASET), benchmark_commit=BENCH,
            model_provider="openai", model_id="model-x", model_parameters={},
            prompt_sha256=file_sha256(prompts[system_id]),
            component_commits=components[system_id], replicate=0,
        )
        target = run_root / system_id / "manifest.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")
    return run_root


def _receipt_file(tmp_path: Path, system_id: str) -> Path:
    target = tmp_path / f"{system_id}.jsonl"
    keys = {
        "B2": ("gremlin",),
        "B3": ("ciel", "execution_gate"),
        "B4": ("gremlin", "ciel", "execution_gate"),
    }[system_id]
    with target.open("w", encoding="utf-8") as handle:
        for task in load_tasks(DATASET):
            row = {"task_id": task.task_id}
            for key in keys:
                row[key] = {"schema": f"TEST_{key.upper()}", "commitment": "x"}
            handle.write(json.dumps(row) + "\n")
    return target


def _prompts():
    return {"B0": P0, "B1": P13, "B2": P24, "B3": P13, "B4": P24}


def test_preflight_passes_with_complete_reproducible_inputs(tmp_path: Path) -> None:
    run_root = _make_run_root(tmp_path)
    receipts = {sid: _receipt_file(tmp_path, sid) for sid in ("B2", "B3", "B4")}
    report = preflight_live(
        dataset=DATASET, run_root=run_root, prompt_paths=_prompts(),
        receipt_paths=receipts, require_api_key=False,
        api_key_env="CIEL_TEST_KEY_THAT_IS_NOT_SET",
    )
    assert report.status == "PASS"
    assert report.task_count == 60
    assert report.issues == ()
    assert any("credential absent" in warning for warning in report.warnings)


def test_preflight_fails_closed_on_missing_receipts_and_api_key(tmp_path: Path) -> None:
    report = preflight_live(
        dataset=DATASET, run_root=_make_run_root(tmp_path), prompt_paths=_prompts(),
        receipt_paths={}, require_api_key=True,
        api_key_env="CIEL_TEST_KEY_THAT_IS_NOT_SET",
    )
    assert report.status == "FAIL"
    assert any("B2: receipt bundle path not supplied" in issue for issue in report.issues)
    assert any("B3: receipt bundle path not supplied" in issue for issue in report.issues)
    assert any("B4: receipt bundle path not supplied" in issue for issue in report.issues)
    assert any("API credential missing" in issue for issue in report.issues)
