from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .dynamic_gate import CIEL_EXECUTION_CONTRACT_SCHEMA, execution_contract_sha256
from .schema import Task


SCHEMA = "CIEL_NATIVE_BENCHMARK_RECEIPT_V0_1"
ANALYSIS_SCHEMA = "CIEL_NATIVE_ANALYSIS_V0_1"

_OPERATOR_TO_TOOL: dict[str, str] = {
    "GIVES": "transfer_object",
    "NAMES": "rename_entity",
    "DESCRIBES": "describe_entity",
    "SPEAKS_ABOUT": "record_relation",
    "CONNECTED_WITH": "record_relation",
    "BELONGS_TO": "record_relation",
    "ADDRESSES": "address_person",
}

_ROLE_TO_ARGUMENT: dict[str, dict[str, str]] = {
    "GIVES": {
        "giver": "sender",
        "recipient": "recipient",
        "transferred_object": "object",
    },
    "NAMES": {
        "namer": "namer",
        "entity_named": "entity",
        "assigned_name": "new_name",
    },
    "DESCRIBES": {
        "describer": "describer",
        "described_object": "entity",
    },
    "SPEAKS_ABOUT": {
        "speaker": "speaker",
        "topic": "topic",
        "interlocutor": "interlocutor",
    },
    "CONNECTED_WITH": {
        "entity": "entity",
        "counterpart_in_relation": "counterpart",
    },
    "BELONGS_TO": {
        "member_or_part": "member_or_part",
        "container_or_owner": "container_or_owner",
    },
    "ADDRESSES": {
        "addressee": "addressee",
    },
}

_REQUIRED_ARGUMENTS: dict[str, tuple[str, ...]] = {
    "GIVES": ("sender", "recipient", "object"),
    "NAMES": ("namer", "entity", "new_name"),
    "DESCRIBES": ("describer", "entity", "description"),
    "SPEAKS_ABOUT": ("speaker", "interlocutor", "topic", "operator"),
    "CONNECTED_WITH": ("entity", "counterpart", "operator"),
    "BELONGS_TO": ("member_or_part", "container_or_owner", "operator"),
    "ADDRESSES": ("addressee", "utterance"),
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


def _collect_world_strings(value: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str) and key:
                out.add(key)
            out.update(_collect_world_strings(child))
    elif isinstance(value, (list, tuple, set, frozenset)):
        for child in value:
            out.update(_collect_world_strings(child))
    elif isinstance(value, str) and value:
        out.add(value)
    return out


def _canonical_world_entity(label: str, world_state: Mapping[str, Any]) -> str | None:
    text = str(label).strip()
    if not text:
        return None

    speaker = world_state.get("speaker")
    if text.casefold() in {"ja", "@speaker", "@implicit_subject"} and isinstance(speaker, str) and speaker:
        return speaker

    candidates = _collect_world_strings(world_state)
    exact = [candidate for candidate in candidates if candidate.casefold() == text.casefold()]
    if len(exact) == 1:
        return exact[0]

    aliases = world_state.get("aliases")
    if isinstance(aliases, Mapping):
        matches = [
            str(canonical)
            for canonical, surface in aliases.items()
            if isinstance(surface, str) and surface.casefold() == text.casefold()
        ]
        if len(matches) == 1:
            return matches[0]
    return None


def native_ciel_analysis(task: Task) -> Mapping[str, Any]:
    """Run the pinned CIELingo -> Semantic validation path without benchmark truth."""
    if task.language.lower() not in {"pl", "polish"}:
        return {
            "schema": ANALYSIS_SCHEMA,
            "language": task.language,
            "text": task.user_input,
            "status": "LANGUAGE_UNSUPPORTED_BY_PINNED_CIEL",
            "ground_truth_used": False,
        }

    try:
        import cielingo_core
        from cielingo_core.language_spaces.pl.solver import PolishRegionalSolver
        from cielingo_core.lingophysics.sentence_equation import calculate_sentence_equation
        from ciel_semantic_model.relation_hypergraph_bridge import validate_relation_hypergraph
    except ImportError as exc:
        raise RuntimeError(
            "Pinned CIELingo and Ciel-Semantic-Model packages are required to build CIEL receipts"
        ) from exc

    repo_root = Path(cielingo_core.__file__).resolve().parents[2]
    result = PolishRegionalSolver(repo_root).solve(task.user_input)
    equation = calculate_sentence_equation(result)
    equation_issues = equation.validate()
    if equation_issues:
        raise ValueError("CIEL SentenceEquation validation failed: " + "; ".join(equation_issues))
    equation_payload = equation.to_dict()
    hypergraph = validate_relation_hypergraph(equation_payload)
    return {
        "schema": ANALYSIS_SCHEMA,
        "language": task.language,
        "text": task.user_input,
        "status": "CIEL_ANALYSIS_COMPLETE",
        "sentence_equation": equation_payload,
        "relation_hypergraph_validation": hypergraph.to_dict(),
        "ground_truth_used": False,
    }


def _blocking_contract(status: str, reason: str) -> dict[str, Any]:
    return {
        "schema": CIEL_EXECUTION_CONTRACT_SCHEMA,
        "status": status,
        "tool": None,
        "required_arguments": [],
        "argument_bindings": {},
        "allow_extra_arguments": False,
        "reason": reason,
    }


def project_execution_contract(task: Task, analysis: Mapping[str, Any]) -> dict[str, Any]:
    """Project only semantics established by the native analysis and world state."""
    if analysis.get("ground_truth_used") is not False:
        raise ValueError("CIEL analysis must explicitly declare ground_truth_used=false")
    if analysis.get("status") != "CIEL_ANALYSIS_COMPLETE":
        return _blocking_contract("AMBIGUOUS", str(analysis.get("status") or "CIEL_ANALYSIS_UNAVAILABLE"))

    equation = analysis.get("sentence_equation")
    validation = analysis.get("relation_hypergraph_validation")
    if not isinstance(equation, Mapping) or not isinstance(validation, Mapping):
        return _blocking_contract("AMBIGUOUS", "CIEL_ANALYSIS_INCOMPLETE")
    if validation.get("valid") is not True:
        return _blocking_contract("AMBIGUOUS", "NO_VALID_TYPED_RELATION_HYPERGRAPH")

    graph = equation.get("relation_hypergraph")
    if not isinstance(graph, Mapping):
        return _blocking_contract("AMBIGUOUS", "RELATION_HYPERGRAPH_ABSENT")
    events = graph.get("events")
    incidences = graph.get("incidences")
    entities = graph.get("entities")
    if not isinstance(events, list) or len(events) != 1 or not isinstance(incidences, list) or not isinstance(entities, list):
        return _blocking_contract("AMBIGUOUS", "RELATION_EVENT_CARDINALITY_UNRESOLVED")

    event = events[0]
    if not isinstance(event, Mapping):
        return _blocking_contract("AMBIGUOUS", "RELATION_EVENT_INVALID")
    operator = str(event.get("operator") or "").upper()
    tool = _OPERATOR_TO_TOOL.get(operator)
    role_map = _ROLE_TO_ARGUMENT.get(operator)
    required = _REQUIRED_ARGUMENTS.get(operator)
    if not tool or role_map is None or required is None:
        return _blocking_contract("AMBIGUOUS", "OPERATOR_NOT_MAPPED_TO_EXECUTION_CONTRACT")
    if tool not in task.allowed_tools:
        return _blocking_contract("POLICY_REJECT", "OPERATOR_TOOL_NOT_ALLOWED_BY_TASK")

    entity_by_id = {
        str(row.get("entity_id")): row
        for row in entities
        if isinstance(row, Mapping) and row.get("entity_id")
    }
    bindings: dict[str, Any] = {}
    for incidence in incidences:
        if not isinstance(incidence, Mapping):
            return _blocking_contract("AMBIGUOUS", "INCIDENCE_INVALID")
        argument_name = role_map.get(str(incidence.get("operator_role") or ""))
        if argument_name is None:
            continue
        entity = entity_by_id.get(str(incidence.get("entity_id") or ""))
        if not isinstance(entity, Mapping):
            return _blocking_contract("AMBIGUOUS", "INCIDENCE_ENTITY_UNRESOLVED")
        canonical = _canonical_world_entity(str(entity.get("label") or ""), task.world_state)
        if canonical is None:
            return _blocking_contract("AMBIGUOUS", f"WORLD_ENTITY_UNRESOLVED:{argument_name}")
        bindings[argument_name] = canonical

    if operator in {"SPEAKS_ABOUT", "CONNECTED_WITH", "BELONGS_TO"}:
        bindings["operator"] = operator

    missing = [name for name in required if name not in bindings]
    if missing:
        return {
            "schema": CIEL_EXECUTION_CONTRACT_SCHEMA,
            "status": "MISSING_ARGUMENT",
            "tool": None,
            "required_arguments": list(required),
            "argument_bindings": bindings,
            "allow_extra_arguments": False,
            "reason": "CIEL_TYPED_RELATION_DOES_NOT_BIND_ALL_TOOL_ARGUMENTS",
            "missing_arguments": missing,
        }

    return {
        "schema": CIEL_EXECUTION_CONTRACT_SCHEMA,
        "status": "READY",
        "tool": tool,
        "required_arguments": list(required),
        "argument_bindings": bindings,
        "allow_extra_arguments": False,
        "reason": "CIEL_TYPED_RELATION_AND_WORLD_BINDINGS_COMPLETE",
    }


def build_ciel_receipt(task: Task, analyzer: Callable[[Task], Mapping[str, Any]] = native_ciel_analysis) -> dict[str, Any]:
    analysis = dict(analyzer(task))
    contract = project_execution_contract(task, analysis)
    source_commitment = _sha256_json({
        "schema": ANALYSIS_SCHEMA,
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


def build_ciel_receipt_rows(
    tasks: Iterable[Task],
    analyzer: Callable[[Task], Mapping[str, Any]] = native_ciel_analysis,
) -> list[dict[str, Any]]:
    return [
        {"task_id": task.task_id, "ciel": build_ciel_receipt(task, analyzer)}
        for task in tasks
    ]


def write_ciel_receipt_bundle(
    tasks: Iterable[Task],
    output_path: str | Path,
    analyzer: Callable[[Task], Mapping[str, Any]] = native_ciel_analysis,
) -> dict[str, Any]:
    rows = build_ciel_receipt_rows(tasks, analyzer)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(_canonical_json(row) + "\n")
    tmp.replace(path)
    return {
        "schema": "CIEL_GREMLIN_CIEL_RECEIPT_BUNDLE_V0_1",
        "task_count": len(rows),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "output": str(path),
    }


__all__ = [
    "ANALYSIS_SCHEMA",
    "SCHEMA",
    "build_ciel_receipt",
    "build_ciel_receipt_rows",
    "native_ciel_analysis",
    "project_execution_contract",
    "write_ciel_receipt_bundle",
]
