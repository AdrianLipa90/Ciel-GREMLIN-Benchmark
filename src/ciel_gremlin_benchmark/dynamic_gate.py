from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import string
from typing import Any, Mapping

from .schema import Decision, Task


CIEL_EXECUTION_CONTRACT_SCHEMA = "CIEL_EXECUTION_CONTRACT_V0_1"
CIEL_DYNAMIC_GATE_SCHEMA = "CIEL_DYNAMIC_EXECUTION_GATE_V0_1"
_ALLOWED_STATUSES = frozenset({
    "READY",
    "AMBIGUOUS",
    "MISSING_ARGUMENT",
    "MISSING_EVIDENCE",
    "CONTRADICTORY",
    "POLICY_REJECT",
})
_BLOCKING_ACTIONS = {
    "AMBIGUOUS": "ASK",
    "MISSING_ARGUMENT": "ASK",
    "MISSING_EVIDENCE": "DEFER",
    "CONTRADICTORY": "DEFER",
    "POLICY_REJECT": "REJECT",
}
_HEX = frozenset(string.hexdigits)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _is_sha256(value: object) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in _HEX for char in text)


def execution_contract_sha256(contract: Mapping[str, Any]) -> str:
    """Commit exactly the semantic execution projection consumed by the gate."""
    return _sha256_json(dict(contract))


def validate_ciel_receipt(receipt: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    if not isinstance(receipt, Mapping):
        return ["CIEL receipt must be an object"]
    if receipt.get("candidate_only") is not True:
        issues.append("CIEL receipt must remain candidate_only=true")
    if not _is_sha256(receipt.get("source_commitment")):
        issues.append("CIEL receipt source_commitment must be SHA-256")

    contract = receipt.get("execution_contract")
    if not isinstance(contract, Mapping):
        issues.append("CIEL receipt requires execution_contract object")
        return issues
    if contract.get("schema") != CIEL_EXECUTION_CONTRACT_SCHEMA:
        issues.append("CIEL execution_contract schema mismatch")

    status = str(contract.get("status") or "").upper()
    if status not in _ALLOWED_STATUSES:
        issues.append("CIEL execution_contract status is invalid")

    required_raw = contract.get("required_arguments", [])
    if not isinstance(required_raw, list) or any(not isinstance(item, str) or not item for item in required_raw):
        issues.append("CIEL required_arguments must be a list of non-empty strings")
        required: list[str] = []
    else:
        required = list(required_raw)
        if len(set(required)) != len(required):
            issues.append("CIEL required_arguments must be unique")

    bindings = contract.get("argument_bindings", {})
    if not isinstance(bindings, Mapping):
        issues.append("CIEL argument_bindings must be an object")
        bindings = {}

    allow_extra = contract.get("allow_extra_arguments", False)
    if not isinstance(allow_extra, bool):
        issues.append("CIEL allow_extra_arguments must be boolean")

    tool = contract.get("tool")
    if status == "READY":
        if not isinstance(tool, str) or not tool.strip():
            issues.append("READY CIEL contract requires a tool")
        missing_bindings = [name for name in required if name not in bindings]
        if missing_bindings:
            issues.append("READY CIEL contract lacks required argument bindings")
    elif tool not in (None, ""):
        issues.append("blocking CIEL contract must not prescribe an executable tool")

    expected_sha = receipt.get("execution_contract_sha256")
    if not _is_sha256(expected_sha):
        issues.append("CIEL execution_contract_sha256 must be SHA-256")
    elif expected_sha != execution_contract_sha256(contract):
        issues.append("CIEL execution_contract commitment mismatch")
    return issues


def proposal_sha256(decision: Decision, tool: str | None, arguments: Mapping[str, Any]) -> str:
    return _sha256_json({
        "decision": decision.value,
        "tool": tool,
        "arguments": dict(arguments),
    })


@dataclass(frozen=True)
class DynamicGateResult:
    action: str
    reasons: tuple[str, ...]
    proposal_sha256: str
    source_commitment: str
    execution_contract_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CIEL_DYNAMIC_GATE_SCHEMA,
            "action": self.action,
            "reasons": list(self.reasons),
            "proposal_sha256": self.proposal_sha256,
            "source_commitment": self.source_commitment,
            "execution_contract_sha256": self.execution_contract_sha256,
            "changed": self.action != "ALLOW",
            "ground_truth_used": False,
        }


class DynamicCIELExecutionGate:
    """Evaluate the model proposal against a pre-model CIEL semantic contract.

    The gate never receives benchmark ground truth and never repairs a proposal.
    It may only preserve it (ALLOW) or stop execution with ASK/REJECT/DEFER.
    """

    def evaluate(
        self,
        task: Task,
        decision: Decision,
        tool: str | None,
        arguments: Mapping[str, Any],
        ciel_receipt: Mapping[str, Any],
    ) -> dict[str, Any]:
        del task  # Deliberately unavailable to decision logic beyond proposal context.
        issues = validate_ciel_receipt(ciel_receipt)
        if issues:
            raise ValueError("invalid CIEL receipt: " + "; ".join(issues))

        contract = dict(ciel_receipt["execution_contract"])
        status = str(contract["status"]).upper()
        proposal_commitment = proposal_sha256(decision, tool, arguments)
        source_commitment = str(ciel_receipt["source_commitment"])
        contract_commitment = str(ciel_receipt["execution_contract_sha256"])

        def result(action: str, *reasons: str) -> dict[str, Any]:
            return DynamicGateResult(
                action=action,
                reasons=tuple(reasons),
                proposal_sha256=proposal_commitment,
                source_commitment=source_commitment,
                execution_contract_sha256=contract_commitment,
            ).to_dict()

        # A semantic firewall must not turn a conservative model response into an
        # execution. ASK/REJECT/DEFER are therefore preserved exactly.
        if decision is not Decision.EXECUTE:
            return result("ALLOW", "CONSERVATIVE_NON_EXECUTION_PRESERVED")

        if status != "READY":
            return result(_BLOCKING_ACTIONS[status], f"CIEL_SEMANTIC_STATUS_{status}")

        expected_tool = str(contract["tool"])
        if tool != expected_tool:
            return result("REJECT", "TOOL_MISMATCH")

        required = tuple(contract.get("required_arguments", []))
        actual = dict(arguments)
        missing = [name for name in required if name not in actual]
        if missing:
            return result("ASK", "MISSING_REQUIRED_ARGUMENT")

        bindings = dict(contract.get("argument_bindings", {}))
        mismatched = [name for name, expected in bindings.items() if actual.get(name) != expected]
        if mismatched:
            return result("REJECT", "ARGUMENT_BINDING_MISMATCH")

        if not bool(contract.get("allow_extra_arguments", False)):
            allowed = set(bindings) | set(required)
            if set(actual) - allowed:
                return result("REJECT", "UNEXPECTED_ARGUMENT")

        return result("ALLOW", "SEMANTIC_CONTRACT_MATCH")


__all__ = [
    "CIEL_DYNAMIC_GATE_SCHEMA",
    "CIEL_EXECUTION_CONTRACT_SCHEMA",
    "DynamicCIELExecutionGate",
    "execution_contract_sha256",
    "proposal_sha256",
    "validate_ciel_receipt",
]
