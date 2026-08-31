from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .schema import Prediction


@dataclass(frozen=True)
class SystemContract:
    system_id: str
    label: str
    structured_output: bool
    gremlin: bool
    ciel: bool
    execution_gate: bool
    required_receipts: tuple[str, ...] = ()
    required_components: tuple[str, ...] = ()


SYSTEM_CONTRACTS: Mapping[str, SystemContract] = {
    "B0": SystemContract(
        system_id="B0",
        label="Direct LLM agent",
        structured_output=False,
        gremlin=False,
        ciel=False,
        execution_gate=False,
    ),
    "B1": SystemContract(
        system_id="B1",
        label="LLM + structured/function schema",
        structured_output=True,
        gremlin=False,
        ciel=False,
        execution_gate=False,
        required_receipts=("structured_output",),
    ),
    "B2": SystemContract(
        system_id="B2",
        label="LLM + GREMLIN research/audit",
        structured_output=True,
        gremlin=True,
        ciel=False,
        execution_gate=False,
        required_receipts=("structured_output", "gremlin"),
        required_components=("gremlin",),
    ),
    "B3": SystemContract(
        system_id="B3",
        label="LLM + CIEL semantic control",
        structured_output=True,
        gremlin=False,
        ciel=True,
        execution_gate=True,
        required_receipts=("structured_output", "ciel", "execution_gate"),
        required_components=("cielingo", "ciel_semantic"),
    ),
    "B4": SystemContract(
        system_id="B4",
        label="LLM + GREMLIN + CIEL",
        structured_output=True,
        gremlin=True,
        ciel=True,
        execution_gate=True,
        required_receipts=("structured_output", "gremlin", "ciel", "execution_gate"),
        required_components=("gremlin", "cielingo", "ciel_semantic"),
    ),
}


def get_system_contract(system_id: str) -> SystemContract:
    try:
        return SYSTEM_CONTRACTS[system_id]
    except KeyError as exc:
        raise ValueError(f"unknown benchmark system_id={system_id!r}") from exc


def validate_prediction_contract(prediction: Prediction) -> list[str]:
    contract = get_system_contract(prediction.system_id)
    receipts = dict(prediction.receipts)
    issues: list[str] = []
    for name in contract.required_receipts:
        value = receipts.get(name)
        if value in (None, {}, [], ""):
            issues.append(f"{prediction.system_id} requires receipt {name!r}")
    return issues
