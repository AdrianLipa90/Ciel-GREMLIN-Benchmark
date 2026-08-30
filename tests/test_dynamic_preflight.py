from __future__ import annotations

import json
from pathlib import Path

from ciel_gremlin_benchmark.dataset import dataset_sha256, load_tasks
from ciel_gremlin_benchmark.dynamic_gate import (
    CIEL_EXECUTION_CONTRACT_SCHEMA,
    execution_contract_sha256,
)
from ciel_gremlin_benchmark.dynamic_preflight import dynamic_preflight_live
from ciel_gremlin_benchmark.manifest import RunManifest, file_sha256


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
            run_id=f"dynamic-{system_id}",
            system_id=system_id,
            dataset_sha256=dataset_sha256(DATASET),
            benchmark_commit=BENCH,
            model_provider="openai",
            model_id="model-x",
            model_parameters={},
            prompt_sha256=file_sha256(prompts[system_id]),
            component_commits=components[system_id],
            replicate=0,
        )
        target = run_root / system_id / "manifest.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")
    return run_root


def _ciel() -> dict:
    contract = {
        "schema": CIEL_EXECUTION_CONTRACT_SCHEMA,
        "status": "MISSING_EVIDENCE",
        "tool": None,
        "required_arguments": [],
        "argument_bindings": {},
        "allow_extra_arguments": False,
    }
    return {
        "candidate_only": True,
        "ground_truth_used": False,
        "source_commitment": "d" * 64,
        "execution_contract": contract,
        "execution_contract_sha256": execution_contract_sha256(contract),
    }


def _bundle(tmp_path: Path, system_id: str, *, static_gate=False, contaminate=False, tamper=False) -> Path:
    path = tmp_path / f"{system_id}.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for task in load_tasks(DATASET):
            row = {"task_id": task.task_id}
            if system_id in {"B2", "B4"}:
                row["gremlin"] = {"schema": "GREMLIN_RESEARCH_EXECUTOR_V0_1", "status": "TEST"}
            if system_id in {"B3", "B4"}:
                receipt = _ciel()
                if tamper:
                    receipt["execution_contract"]["status"] = "READY"
                row["ciel"] = receipt
            if system_id == "B3" and contaminate:
                row["gremlin"] = {"schema": "SHOULD_NOT_BE_HERE"}
            if static_gate:
                row["execution_gate"] = {"action": "ALLOW"}
            handle.write(json.dumps(row) + "\n")
    return path


def _prompts():
    return {"B0": P0, "B1": P13, "B2": P24, "B3": P13, "B4": P24}


def test_dynamic_preflight_passes_without_precomputed_gate(tmp_path: Path) -> None:
    receipts = {sid: _bundle(tmp_path, sid) for sid in ("B2", "B3", "B4")}
    report = dynamic_preflight_live(
        dataset=DATASET,
        run_root=_make_run_root(tmp_path),
        prompt_paths=_prompts(),
        receipt_paths=receipts,
        require_api_key=False,
        api_key_env="CIEL_DYNAMIC_TEST_KEY_NOT_SET",
    )
    assert report.status == "PASS"
    assert report.task_count == 60
    assert report.issues == ()
    assert any("credential absent" in warning for warning in report.warnings)


def test_dynamic_preflight_rejects_precomputed_execution_gate(tmp_path: Path) -> None:
    receipts = {
        "B2": _bundle(tmp_path, "B2"),
        "B3": _bundle(tmp_path, "B3", static_gate=True),
        "B4": _bundle(tmp_path, "B4"),
    }
    report = dynamic_preflight_live(
        dataset=DATASET, run_root=_make_run_root(tmp_path), prompt_paths=_prompts(),
        receipt_paths=receipts, require_api_key=False,
        api_key_env="CIEL_DYNAMIC_TEST_KEY_NOT_SET",
    )
    assert report.status == "FAIL"
    assert any("precomputed execution_gate is forbidden" in issue for issue in report.issues)


def test_dynamic_preflight_rejects_ablation_contamination(tmp_path: Path) -> None:
    receipts = {
        "B2": _bundle(tmp_path, "B2"),
        "B3": _bundle(tmp_path, "B3", contaminate=True),
        "B4": _bundle(tmp_path, "B4"),
    }
    report = dynamic_preflight_live(
        dataset=DATASET, run_root=_make_run_root(tmp_path), prompt_paths=_prompts(),
        receipt_paths=receipts, require_api_key=False,
        api_key_env="CIEL_DYNAMIC_TEST_KEY_NOT_SET",
    )
    assert report.status == "FAIL"
    assert any("contaminates CIEL-only ablation" in issue for issue in report.issues)


def test_dynamic_preflight_rejects_tampered_ciel_contract(tmp_path: Path) -> None:
    receipts = {
        "B2": _bundle(tmp_path, "B2"),
        "B3": _bundle(tmp_path, "B3", tamper=True),
        "B4": _bundle(tmp_path, "B4"),
    }
    report = dynamic_preflight_live(
        dataset=DATASET, run_root=_make_run_root(tmp_path), prompt_paths=_prompts(),
        receipt_paths=receipts, require_api_key=False,
        api_key_env="CIEL_DYNAMIC_TEST_KEY_NOT_SET",
    )
    assert report.status == "FAIL"
    assert any("commitment mismatch" in issue for issue in report.issues)


def test_dynamic_preflight_still_requires_api_key_for_network_run(tmp_path: Path) -> None:
    receipts = {sid: _bundle(tmp_path, sid) for sid in ("B2", "B3", "B4")}
    report = dynamic_preflight_live(
        dataset=DATASET, run_root=_make_run_root(tmp_path), prompt_paths=_prompts(),
        receipt_paths=receipts, require_api_key=True,
        api_key_env="CIEL_DYNAMIC_TEST_KEY_NOT_SET",
    )
    assert report.status == "FAIL"
    assert any("API credential missing" in issue for issue in report.issues)
