from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from . import ciel_action_scope as scoped
from . import ciel_receipts as base
from .dynamic_gate import execution_contract_sha256
from .schema import Task


SCHEMA = "CIEL_WORLD_STATE_SCOPED_BENCHMARK_RECEIPT_V0_2"
WORLD_INDEX_SCHEMA = "CIEL_WORLD_STATE_INDEX_V0_1"
WORLD_GROUNDING_SCHEMA = "CIEL_RELATION_WORLD_STATE_GROUNDING_BUNDLE_V0_1"
_ALLOWED_SOURCE = frozenset({"BOUND", "AMBIGUOUS", "UNBOUND", "IMPLICIT"})
_ALLOWED_RESOLUTION = frozenset({
    "RESOLVED_CARD_ID",
    "RESOLVED_WORLD_STATE_INDEX",
    "RESOLVED_IMPLICIT_SPEAKER",
    "AMBIGUOUS_PRODUCER_IDENTITY",
    "AMBIGUOUS_CARD_WORLD",
    "AMBIGUOUS_WORLD_STATE_INDEX",
    "UNRESOLVED_CARD_ID",
    "UNRESOLVED_WORLD_STATE",
    "UNRESOLVED_IMPLICIT_SPEAKER",
})


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


def _validate_world_state_index(index: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(index, Mapping):
        return ["world_state_index must be an object"]
    issues: list[str] = []
    if index.get("schema") != WORLD_INDEX_SCHEMA:
        issues.append("world_state_index schema mismatch")
    records = index.get("records")
    references = index.get("references")
    if not isinstance(records, list):
        issues.append("world_state_index records must be a list")
        records = []
    if not isinstance(references, list):
        issues.append("world_state_index references must be a list")
        references = []
    ids = [
        str(row.get("canonical_id") or "")
        for row in records
        if isinstance(row, Mapping)
    ]
    if len(ids) != len(records):
        issues.append("world_state_index records must contain objects")
    if any(not item for item in ids):
        issues.append("world_state_index canonical IDs must be non-empty")
    if len(set(ids)) != len(ids):
        issues.append("world_state_index canonical IDs must be unique")
    commitment = index.get("commitment")
    body = {
        "schema": index.get("schema"),
        "records": records,
        "references": references,
    }
    if not _is_sha256(commitment):
        issues.append("world_state_index commitment must be SHA-256")
    elif commitment != _sha256_json(body):
        issues.append("world_state_index commitment mismatch")
    return issues


def validate_world_grounding_payload(
    equation: Mapping[str, Any],
    grounding: Mapping[str, Any] | None,
    world_state_index: Mapping[str, Any] | None,
) -> list[str]:
    issues = _validate_world_state_index(world_state_index)
    if not isinstance(grounding, Mapping):
        return [*issues, "relation_world_state_grounding must be an object"]
    if grounding.get("schema") != WORLD_GROUNDING_SCHEMA:
        issues.append("relation_world_state_grounding schema mismatch")
    if grounding.get("candidate_only") is not True:
        issues.append("relation_world_state_grounding must remain candidate_only=true")

    graph = equation.get("relation_hypergraph")
    cards = equation.get("relation_entity_card_bindings")
    if not isinstance(graph, Mapping) or not isinstance(cards, Mapping):
        issues.append("relation world grounding requires graph and card receipts")
        return issues
    if grounding.get("equation_id") != equation.get("equation_id"):
        issues.append("relation world grounding equation_id mismatch")
    if grounding.get("language_id") != equation.get("language_id"):
        issues.append("relation world grounding language mismatch")
    if grounding.get("relation_hypergraph_commitment") != graph.get("commitment"):
        issues.append("relation world grounding hypergraph commitment mismatch")
    if grounding.get("card_bindings_commitment") != cards.get("commitment"):
        issues.append("relation world grounding card commitment mismatch")
    if isinstance(world_state_index, Mapping) and (
        grounding.get("world_state_index_commitment") != world_state_index.get("commitment")
    ):
        issues.append("relation world grounding world-state commitment mismatch")

    entries = grounding.get("entries")
    if not isinstance(entries, list):
        issues.append("relation world grounding entries must be a list")
        entries = []
    graph_entities = graph.get("entities")
    graph_ids: set[str] = set()
    if not isinstance(graph_entities, list):
        issues.append("relation hypergraph entities must be a list")
    else:
        for row in graph_entities:
            if not isinstance(row, Mapping) or not row.get("entity_id"):
                issues.append("relation hypergraph entity is invalid")
                continue
            graph_ids.add(str(row["entity_id"]))

    entry_ids: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            issues.append(f"relation world grounding entries[{index}] must be an object")
            continue
        entity_id = str(entry.get("entity_id") or "")
        if not entity_id:
            issues.append(f"relation world grounding entries[{index}].entity_id is required")
        entry_ids.append(entity_id)
        source_status = str(entry.get("source_status") or "")
        if source_status not in _ALLOWED_SOURCE:
            issues.append(f"relation world grounding entries[{index}] source_status invalid")
        resolution = str(entry.get("resolution_status") or "")
        if resolution not in _ALLOWED_RESOLUTION:
            issues.append(f"relation world grounding entries[{index}] resolution_status invalid")
        resolved = resolution.startswith("RESOLVED_")
        world_entity = entry.get("world_entity")
        if resolved and (not isinstance(world_entity, str) or not world_entity):
            issues.append(f"relation world grounding entries[{index}] resolved without world_entity")
        if not resolved and world_entity is not None:
            issues.append(f"relation world grounding entries[{index}] unresolved with world_entity")
        card_id = entry.get("card_id")
        if source_status == "BOUND" and (not isinstance(card_id, str) or not card_id):
            issues.append(f"relation world grounding entries[{index}] BOUND requires card_id")
        if source_status != "BOUND" and card_id is not None:
            issues.append(f"relation world grounding entries[{index}] non-BOUND carries card_id")
        if entry.get("candidate_only") is not True:
            issues.append(f"relation world grounding entries[{index}] candidate_only must be true")
    if len(set(entry_ids)) != len(entry_ids):
        issues.append("relation world grounding entity IDs must be unique")
    if graph_ids and set(entry_ids) != graph_ids:
        issues.append("relation world grounding entity partition mismatch")

    body = {
        "schema": grounding.get("schema"),
        "equation_id": grounding.get("equation_id"),
        "language_id": grounding.get("language_id"),
        "relation_hypergraph_commitment": grounding.get("relation_hypergraph_commitment"),
        "card_bindings_commitment": grounding.get("card_bindings_commitment"),
        "world_state_index_commitment": grounding.get("world_state_index_commitment"),
        "entries": entries,
        "candidate_only": grounding.get("candidate_only"),
    }
    commitment = grounding.get("commitment")
    if not _is_sha256(commitment):
        issues.append("relation world grounding commitment must be SHA-256")
    elif commitment != _sha256_json(body):
        issues.append("relation world grounding commitment mismatch")
    return issues


def _legacy_compat_grounding(
    equation: Mapping[str, Any],
    grounding: Mapping[str, Any],
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for entry in grounding.get("entries", []):
        resolution = str(entry.get("resolution_status") or "")
        resolved = resolution.startswith("RESOLVED_")
        entries.append({
            "entity_id": entry.get("entity_id"),
            "source_status": entry.get("source_status"),
            "binding_id": None,
            "card_id": entry.get("card_id"),
            "grounding": {
                "status": resolution,
                "world_entity": entry.get("world_entity") if resolved else None,
            },
            "candidate_only": True,
        })
    graph = equation["relation_hypergraph"]
    cards = equation["relation_entity_card_bindings"]
    return {
        "schema": base.GROUNDING_SCHEMA,
        "equation_id": equation.get("equation_id"),
        "language_id": equation.get("language_id"),
        "relation_hypergraph_commitment": graph.get("commitment"),
        "card_bindings_commitment": cards.get("commitment"),
        "entries": entries,
        "candidate_only": True,
        "commitment": "compatibility-view-after-v0.2-validation",
    }


def native_ciel_world_state_analysis(task: Task) -> Mapping[str, Any]:
    """Run scoped CIEL analysis and replace string flattening with native world-state grounding."""
    analysis = dict(scoped.native_ciel_scoped_analysis(task))
    if analysis.get("status") != "CIEL_ANALYSIS_COMPLETE":
        return analysis
    equation = analysis.get("sentence_equation")
    if not isinstance(equation, Mapping):
        return analysis

    try:
        import cielingo_core
        from cielingo_core.regional.simple_solver_utils import load_atlas_cards
        from ciel_semantic_model.relation_world_state_grounding import (
            ground_relation_entities_with_world_state,
        )
        from ciel_semantic_model.world_state_index import WorldStateIndex
    except ImportError as exc:
        raise RuntimeError(
            "Pinned CIEL world-state grounding components are required for v0.2 receipts"
        ) from exc

    repo_root = Path(cielingo_core.__file__).resolve().parents[2]
    atlas_cards = base._load_grounding_atlas(repo_root, load_atlas_cards)
    raw_speaker = task.world_state.get("speaker") if isinstance(task.world_state, Mapping) else None
    speaker = raw_speaker if isinstance(raw_speaker, str) and raw_speaker else None
    index = WorldStateIndex.create(task.world_state)
    grounding = ground_relation_entities_with_world_state(
        equation,
        world_state=task.world_state,
        atlas_cards=atlas_cards,
        speaker=speaker,
    )
    analysis["world_state_index"] = index.to_dict()
    analysis["relation_world_state_grounding"] = (
        None if grounding is None else grounding.to_dict()
    )
    analysis["ground_truth_used"] = False
    return analysis


def project_world_state_execution_contract(
    task: Task,
    analysis: Mapping[str, Any],
) -> dict[str, Any]:
    if analysis.get("ground_truth_used") is not False:
        raise ValueError("CIEL analysis must explicitly declare ground_truth_used=false")
    if analysis.get("status") != "CIEL_ANALYSIS_COMPLETE":
        return base._blocking_contract(
            "AMBIGUOUS",
            str(analysis.get("status") or "CIEL_ANALYSIS_UNAVAILABLE"),
        )
    equation = analysis.get("sentence_equation")
    grounding = analysis.get("relation_world_state_grounding")
    world_index = analysis.get("world_state_index")
    if not isinstance(equation, Mapping):
        return base._blocking_contract("AMBIGUOUS", "CIEL_ANALYSIS_INCOMPLETE")
    issues = validate_world_grounding_payload(
        equation,
        grounding if isinstance(grounding, Mapping) else None,
        world_index if isinstance(world_index, Mapping) else None,
    )
    if issues:
        return base._blocking_contract(
            "AMBIGUOUS",
            "RELATION_WORLD_STATE_GROUNDING_CONTINUITY_FAIL",
        )
    assert isinstance(grounding, Mapping)
    adapted = dict(analysis)
    adapted["relation_entity_grounding"] = _legacy_compat_grounding(equation, grounding)
    return scoped.project_scoped_execution_contract(task, adapted)


def build_world_state_ciel_receipt(
    task: Task,
    analyzer: Callable[[Task], Mapping[str, Any]] = native_ciel_world_state_analysis,
) -> dict[str, Any]:
    analysis = dict(analyzer(task))
    contract = project_world_state_execution_contract(task, analysis)
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


def write_world_state_ciel_receipt_bundle(
    tasks: Iterable[Task],
    output_path: str | Path,
    analyzer: Callable[[Task], Mapping[str, Any]] = native_ciel_world_state_analysis,
) -> dict[str, Any]:
    rows = [
        {"task_id": task.task_id, "ciel": build_world_state_ciel_receipt(task, analyzer)}
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
        "schema": "CIEL_GREMLIN_WORLD_STATE_CIEL_RECEIPT_BUNDLE_V0_2",
        "task_count": len(rows),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "output": str(path),
    }


__all__ = [
    "SCHEMA",
    "WORLD_GROUNDING_SCHEMA",
    "WORLD_INDEX_SCHEMA",
    "build_world_state_ciel_receipt",
    "native_ciel_world_state_analysis",
    "project_world_state_execution_contract",
    "validate_world_grounding_payload",
    "write_world_state_ciel_receipt_bundle",
]
