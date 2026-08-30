import json
import sys
from pathlib import Path

from ciel_gremlin_benchmark.cli import main


def _dataset() -> str:
    return str(Path(__file__).parents[1] / "dataset" / "golden_v0_1.jsonl")


def test_cli_validate_reports_fingerprint(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["ciel-gremlin-benchmark", "validate", _dataset()])
    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PASS"
    assert payload["tasks"] == 60
    assert len(payload["dataset_sha256"]) == 64


def test_cli_sanity_runs(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["ciel-gremlin-benchmark", "sanity", _dataset()])
    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PASS"
    assert payload["systems"]["SANITY_ORACLE"]["reliability_score"] == 1.0
