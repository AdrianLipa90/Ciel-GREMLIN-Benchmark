from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from . import ciel_receipts as base
from .dynamic_gate import execution_contract_sha256
from .schema import Task


SCHEMA = "CIEL_NATIVE_SCOPED_BENCHMARK_RECEIPT_V0_1"
ACTION_SCOPE_GATE_SCHEMA = "CIEL_ACTION_SCOPE_GATE_V0_1"

_ACTION_OPERATORS = frozenset({
    "SEND_EMAIL",
    "ARCHIVES",
    "DELETES",
    "UPDATES_RECORD",
    "APPROVES_SUPPLIER",
    "CREATES_CONTRACT_WITH",
})

_ACTION_OPERATOR_TO_TOOL: dict[str, str] = {
    "SEND_EMAIL": "send_email",
    "ARCHIVES": "archive_file",
    "DELETES": "delete_file",
    "UPDATES_RECORD": "update_record",
    "APPROVES_SUPPLIER": "approve_supplier",
    "CREATES_CONTRACT_WITH": "create_contract",
}

_ACTION_ROLE_TO_ARGUMENT: dict[str, dict[str, str]] = {
    "SEND_EMAIL": {
        "document": "document",
        "recipient": "recipient",
    },
    "ARCHIVES": {
        "file_or_object": "file",
    },
    "DELETES": {
        "file_or_object": "file",
    },
    "UPDATES_RECORD": {
        "record": "entity",
        "field": "field",
        "value": "value",
    },
    "APPROVES_SUPPLIER": {
        "supplier": "company",
    },
    "CREATES_CONTRACT_WITH": {
        "counterpart": "company",
    },
}

_ACTION_REQUIRED_ARGUMENTS: dict[str, tuple[str, ...]] = {
    "SEND_EMAIL": ("document", "recipient"),
    "ARCHIVES": ("file",),
    "DELETES": ("file",),
    "UPDATES_RECORD": ("entity", "field", "value"),
    "APPROVES_SUPPLIER": ("company",),
    "CREATES_CONTRACT_WITH": ("company",),
}

_SCOPE_STATUS_TO_CONTRACT_STATUS = {
    "NEGATED": "POLICY_REJECT",
    "CONDITIONAL": "MISSING_EVIDENCE",
    "DELAYED": "MISSING_EVIDENCE",
    "QUALIFIED": "MISSING_EVIDENCE",
    "MULTI_ACTION": "AMBIGUOUS",
    "NOT_ACTION": "AMBIGUOUS",
}


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


def _is_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdefABCDEF" for char in text)


def _scope_gate_body(gate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": gate.get("schema"),
        "producer_present": gate.get("producer_present"),
        "producer_valid": gate.get("producer_valid"),
        "recomputation_match": gate.get("recomputation_match"),
        "producer_status": gate.get("producer_status"),
        "recomputed_status": gate.get("recomputed_status"),
        "safe_for_tool_projection": gate.get("safe_for_tool_projection"),
        "reason": gate.get("reason"),
        "surface_commitment": gate.get("surface_commitment"),
        "producer_commitment": gate.get("producer_commitment"),
        "basis": gate.get("basis"),
        "candidate_only": gate.get("candidate_only"),
    }


def validate_scope_gate_payload(gate: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(gate, Mapping):
        return ["action_scope_gate must be an object"]
    issues: list[str] = []
    if gate.get("schema") != ACTION_SCOPE_GATE_SCHEMA:
        issues.append("action_scope_gate schema mismatch")
    if gate.get("candidate_only") is not True:
        issues.append("action_scope_gate must remain candidate_only=true")
    if not _is_sha256(gate.get("surface_commitment")):
        issues.append("action_scope_gate surface_commitment must be SHA-256")
    commitment = gate.get("commitment")
    if not _is_sha256(commitment):
        issues.append("action_scope_gate commitment must be SHA-256")
    elif commitment != _sha256_json(_scope_gate_body(gate)):
        issues.append("action_scope_gate commitment mismatch")

    safe = gate.get("safe_for_tool_projection") is True
    if safe and not (
        gate.get("producer_present") is True
        and gate.get("producer_valid") is True
        and gate.get("recomputation_match") is True
        and gate.get("producer_status") == "SCOPE_SAFE"
        and gate.get("recomputed_status") == "SCOPE_SAFE"
        and gate.get("reason") == "SCOPE_SAFE_EXACT_AGREEMENT"
    ):
        issues.append("action_scope_gate unsafe ALLOW state")
    return issues


def native_ciel_scoped_analysis(task: Task) -> Mapping[str, Any]:
    """Run native CIEL analysis and attach independent action-scope receipts."""
    analysis = dict(base.native_ciel_analysis(task))
    if analysis.get("status") != "CIEL_ANALYSIS_COMPLETE":
        return analysis

    equation = analysis.get("sentence_equation")
    if not isinstance(equation, Mapping):
        return analysis
    tokens = equation.get("tokens")
    language_id = str(equation.get("language_id") or "")
    if language_id != "pl" or not isinstance(tokens, list):
        return analysis

    try:
        from cielingo_core.lingophysics.action_scope_condition import (
            build_action_scope_condition_receipt,
        )
        from ciel_semantic_model.action_scope_condition_gate import (
            validate_action_scope_condition,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Pinned CIEL action scope producer and Semantic scope consumer are required"
        ) from exc

    producer = build_action_scope_condition_receipt(
        task.user_input,
        tokens=tokens,
        language_id=language_id,
    )
    gate = validate_action_scope_condition(
        producer.to_dict(),
        tokens=tokens,
        language_id=language_id,
    )
    analysis["action_scope_condition"] = producer.to_dict()
    analysis["action_scope_gate"] = gate.to_dict()
    return analysis


def _single_event_operator(analysis: Mapping[str, Any]) -> str | None:
    equation = analysis.get("sentence_equation")
    if not isinstance(equation, Mapping):
        return None
    graph = equation.get("relation_hypergraph")
    if not isinstance(graph, Mapping):
        return None
    events = graph.get("events")
    if not isinstance(events, list) or len(events) != 1 or not isinstance(events[0], Mapping):
        return None
    return str(events[0].get("operator") or "").upper() or None


def _scope_blocking_contract(gate: Mapping[str, Any] | None) -> dict[str, Any]:
    issues = validate_scope_gate_payload(gate)
    if issues:
        return base._blocking_contract("AMBIGUOUS", "ACTION_SCOPE_GATE_INVALID")
    assert gate is not None
    if gate.get("safe_for_tool_projection") is True:
        raise ValueError("safe scope gate passed to blocking-contract helper")
    status = str(gate.get("recomputed_status") or "")
    contract_status = _SCOPE_STATUS_TO_CONTRACT_STATUS.get(status, "AMBIGUOUS")
    return base._blocking_contract(contract_status, f"ACTION_SCOPE_{status or 'UNRESOLVED'}")


def project_scoped_execution_contract(
    task: Task,
    analysis: Mapping[str, Any],
) -> dict[str, Any]:
    """Project legacy CIEL relations plus scope-gated v0.2 agent actions."""
    operator = _single_event_operator(analysis)
    if operator not in _ACTION_OPERATORS:
        return base.project_execution_contract(task, analysis)

    if analysis.get("ground_truth_used") is not False:
        raise ValueError("CIEL analysis must explicitly declare ground_truth_used=false")
    if analysis.get("status") != "CIEL_ANALYSIS_COMPLETE":
        return base._blocking_contract(
            "AMBIGUOUS",
            str(analysis.get("status") or "CIEL_ANALYSIS_UNAVAILABLE"),
        )

    gate = analysis.get("action_scope_gate")
    scope_issues = validate_scope_gate_payload(gate if isinstance(gate, Mapping) else None)
    if scope_issues:
        return base._blocking_contract("AMBIGUOUS", "ACTION_SCOPE_GATE_INVALID")
    assert isinstance(gate, Mapping)
    if gate.get("safe_for_tool_projection") is not True:
        return _scope_blocking_contract(gate)

    equation = analysis.get("sentence_equation")
    validation = analysis.get("relation_hypergraph_validation")
    if not isinstance(equation, Mapping) or not isinstance(validation, Mapping):
        return base._blocking_contract("AMBIGUOUS", "CIEL_ANALYSIS_INCOMPLETE")
    if validation.get("valid") is not True:
        return base._blocking_contract("AMBIGUOUS", "NO_VALID_TYPED_RELATION_HYPERGRAPH")

    graph = equation.get("relation_hypergraph")
    if not isinstance(graph, Mapping):
        return base._blocking_contract("AMBIGUOUS", "RELATION_HYPERGRAPH_ABSENT")
    events = graph.get("events")
    incidences = graph.get("incidences")
    entities = graph.get("entities")
    if (
        not isinstance(events, list)
        or len(events) != 1
        or not isinstance(incidences, list)
        or not isinstance(entities, list)
    ):
        return base._blocking_contract(
            "AMBIGUOUS",
            "RELATION_EVENT_CARDINALITY_UNRESOLVED",
        )

    grounding = analysis.get("relation_entity_grounding")
    if not isinstance(grounding, Mapping):
        return base._blocking_contract("AMBIGUOUS", "RELATION_ENTITY_GROUNDING_ABSENT")
    grounding_by_id = base._grounding_entries(equation, grounding)
    if grounding_by_id is None:
        return base._blocking_contract(
            "AMBIGUOUS",
            "RELATION_ENTITY_GROUNDING_CONTINUITY_FAIL",
        )

    event = events[0]
    if not isinstance(event, Mapping):
        return base._blocking_contract("AMBIGUOUS", "RELATION_EVENT_INVALID")
    event_operator = str(event.get("operator") or "").upper()
    if event_operator != operator:
        return base._blocking_contract("AMBIGUOUS", "RELATION_EVENT_OPERATOR_MISMATCH")

    tool = _ACTION_OPERATOR_TO_TOOL[operator]
    role_map = _ACTION_ROLE_TO_ARGUMENT[operator]
    required = _ACTION_REQUIRED_ARGUMENTS[operator]
    if tool not in task.allowed_tools:
        return base._blocking_contract("POLICY_REJECT", "OPERATOR_TOOL_NOT_ALLOWED_BY_TASK")

    entity_by_id = {
        str(row.get("entity_id")): row
        for row in entities
        if isinstance(row, Mapping) and row.get("entity_id")
    }
    bindings: dict[str, Any] = {}
    for incidence in incidences:
        if not isinstance(incidence, Mapping):
            return base._blocking_contract("AMBIGUOUS", "INCIDENCE_INVALID")
        argument_name = role_map.get(str(incidence.get("operator_role") or ""))
        if argument_name is None:
            continue
        entity_id = str(incidence.get("entity_id") or "")
        if entity_id not in entity_by_id:
            return base._blocking_contract("AMBIGUOUS", "INCIDENCE_ENTITY_UNRESOLVED")
        entry = grounding_by_id.get(entity_id)
        if entry is None:
            return base._blocking_contract(
                "AMBIGUOUS",
                f"GROUNDING_ENTRY_MISSING:{argument_name}",
            )
        canonical = base._resolved_world_entity(entry)
        if canonical is None:
            source_status = str(entry.get("source_status") or "UNRESOLVED")
            return base._blocking_contract(
                "AMBIGUOUS",
                f"WORLD_ENTITY_UNRESOLVED:{argument_name}:{source_status}",
            )
        bindings[argument_name] = canonical

    missing = [name for name in required if name not in bindings]
    if missing:
        return {
            "schema": base.CIEL_EXECUTION_CONTRACT_SCHEMA,
            "status": "MISSING_ARGUMENT",
            "tool": None,
            "required_arguments": list(required),
            "argument_bindings": bindings,
            "allow_extra_arguments": False,
            "reason": "CIEL_ACTION_RELATION_DOES_NOT_BIND_ALL_TOOL_ARGUMENTS",
            "missing_arguments": missing,
        }

    return {
        "schema": base.CIEL_EXECUTION_CONTRACT_SCHEMA,
        "status": "READY",
        "tool": tool,
        "required_arguments": list(required),
        "argument_bindings": bindings,
        "allow_extra_arguments": False,
        "reason": "CIEL_SCOPE_SAFE_ACTION_AND_SEMANTIC_GROUNDING_COMPLETE",
    }


def build_scoped_ciel_receipt(
    task: Task,
    analyzer: Callable[[Task], Mapping[str, Any]] = native_ciel_scoped_analysis,
) -> dict[str, Any]:
    analysis = dict(analyzer(task))
    contract = project_scoped_execution_contract(task, analysis)
    source_commitment = _sha256_json({
        "schema": base.ANALYSIS_SCHEMA,
        "task_id": task.task_id,
        "analysis": analysis,
    })
    return {
        "schema": SCHEMA,
        "candidate_only": True,
        "ground_truth_used": False,
        "source_commitment": source_commitment,
        "execution_contract": contract,
        "execution_contract_sha256": execution_contract_sha256(contract),
        "analysis": analysis,
    }


def write_scoped_ciel_receipt_bundle(
    tasks: Iterable[Task],
    output_path: str | Path,
    analyzer: Callable[[Task], Mapping[str, Any]] = native_ciel_scoped_analysis,
) -> dict[str, Any]:
    rows = [
        {"task_id": task.task_id, "ciel": build_scoped_ciel_receipt(task, analyzer)}
        for task in tasks
    ]
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(_canonical_json(row) + "\n")
    tmp.replace(path)
    return {
        "schema": "CIEL_GREMLIN_SCOPED_CIEL_RECEIPT_BUNDLE_V0_1",
        "task_count": len(rows),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "output": str(path),
    }


__all__ = [
    "ACTION_SCOPE_GATE_SCHEMA",
    "SCHEMA",
    "build_scoped_ciel_receipt",
    "native_ciel_scoped_analysis",
    "project_scoped_execution_contract",
    "validate_scope_gate_payload",
    "write_scoped_ciel_receipt_bundle",
]
