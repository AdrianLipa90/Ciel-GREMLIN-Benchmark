import json
import sys
from pathlib import Path

from ciel_gremlin_benchmark.cli import main
from ciel_gremlin_benchmark.manifest import load_manifest


def _dataset() -> str:
    return str(Path(__file__).parents[1] / "dataset" / "golden_v0_1.jsonl")


def test_cli_validate_reports_fingerprint(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["ciel-gremlin-benchmark", "validate", _dataset()],
    )
    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PASS"
    assert payload["tasks"] == 60
    assert len(payload["dataset_sha256"]) == 64


def test_cli_sanity_runs(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["ciel-gremlin-benchmark", "sanity", _dataset()],
    )
    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PASS"
    assert payload["systems"]["SANITY_ORACLE"]["reliability_score"] == 1.0


def test_cli_make_manifest_hashes_exact_prompt_and_dataset(
    monkeypatch, capsys, tmp_path: Path
):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("same prompt bytes\n", encoding="utf-8")
    output = tmp_path / "manifest.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ciel-gremlin-benchmark",
            "make-manifest",
            "--run-id",
            "b4-r0",
            "--system-id",
            "B4",
            "--dataset",
            _dataset(),
            "--benchmark-commit",
            "c" * 40,
            "--model-provider",
            "provider",
            "--model-id",
            "model-x",
            "--model-parameters-json",
            '{"temperature":0,"seed":7}',
            "--prompt",
            str(prompt),
            "--component",
            "gremlin=" + "a" * 40,
            "--component",
            "cielingo=" + "b" * 40,
            "--component",
            "ciel_semantic=" + "e" * 40,
            "--output",
            str(output),
        ],
    )
    assert main() == 0
    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "PASS"
    manifest = load_manifest(output)
    assert manifest.system_id == "B4"
    assert manifest.model_parameters == {"temperature": 0, "seed": 7}
    assert len(manifest.prompt_sha256) == 64
