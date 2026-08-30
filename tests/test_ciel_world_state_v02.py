from __future__ import annotations

from copy import deepcopy

from ciel_gremlin_benchmark.ciel_world_state_v02 import (
    WORLD_GROUNDING_SCHEMA,
    WORLD_INDEX_SCHEMA,
    _sha256_json,
    build_world_state_ciel_receipt,
    project_world_state_execution_contract,
    validate_world_grounding_payload,
)
from ciel_gremlin_benchmark.schema import Decision, GroundTruth
from tests.test_ciel_action_scope import _send_email_analysis, _task as _action_task
from tests.test_ciel_receipts import _gives_analysis, _task as _relation_task


def _world_index(*ids: str) -> dict:
    body = {
        "schema": WORLD_INDEX_SCHEMA,
        "records": [
            {
                "canonical_id": canonical,
                "kind": "entity",
                "aliases": [],
                "roles": [],
                "attributes": [],
            }
            for canonical in sorted(ids)
        ],
        "references": [],
    }
    return {**body, "commitment": _sha256_json(body)}


def _entry(
    entity_id: str,
    source_status: str,
    resolution_status: str,
    world_entity: str | None,
    *,
    card_id: str | None = None,
    basis: str = "TEST_WORLD_STATE_V0_2",
) -> dict:
    return {
        "entity_id": entity_id,
        "source_status": source_status,
        "resolution_status": resolution_status,
        "world_entity": world_entity,
        "card_id": card_id,
        "basis": basis,
        "candidate_world_entities": [],
        "confidence": 1.0 if resolution_status.startswith("RESOLVED_") else 0.0,
        "candidate_only": True,
    }


def _attach_world_grounding(analysis: dict, entries: list[dict], *, index: dict) -> dict:
    equation = analysis["sentence_equation"]
    body = {
        "schema": WORLD_GROUNDING_SCHEMA,
        "equation_id": equation["equation_id"],
        "language_id": equation["language_id"],
        "relation_hypergraph_commitment": equation["relation_hypergraph"]["commitment"],
        "card_bindings_commitment": equation["relation_entity_card_bindings"]["commitment"],
        "world_state_index_commitment": index["commitment"],
        "entries": entries,
        "candidate_only": True,
    }
    analysis["world_state_index"] = index
    analysis["relation_world_state_grounding"] = {
        **body,
        "commitment": _sha256_json(body),
    }
    return analysis


def _gives_world_analysis() -> dict:
    analysis = _gives_analysis(resolved=False)
    return _attach_world_grounding(
        analysis,
        [
            _entry("e1", "IMPLICIT", "RESOLVED_IMPLICIT_SPEAKER", "USER"),
            _entry("e2", "UNBOUND", "RESOLVED_WORLD_STATE_INDEX", "Zosia"),
            _entry("e3", "BOUND", "RESOLVED_CARD_ID", "book", card_id="concept:book"),
        ],
        index=_world_index("USER", "Zosia", "book"),
    )


def _send_world_analysis() -> dict:
    analysis = _send_email_analysis(recipient_resolved=False)
    return _attach_world_grounding(
        analysis,
        [
            _entry("actor", "IMPLICIT", "RESOLVED_IMPLICIT_SPEAKER", "USER"),
            _entry("doc", "BOUND", "RESOLVED_CARD_ID", "report", card_id="concept:report"),
            _entry("recipient", "UNBOUND", "RESOLVED_WORLD_STATE_INDEX", "Zosia"),
        ],
        index=_world_index("USER", "Zosia", "report"),
    )


def test_gives_becomes_ready_when_unbound_recipient_is_resolved_by_world_index() -> None:
    task = _relation_task(world_state={"entities": ["Zosia", "book"], "speaker": "USER"})
    contract = project_world_state_execution_contract(task, _gives_world_analysis())
    assert contract["status"] == "READY"
    assert contract["tool"] == "transfer_object"
    assert contract["argument_bindings"] == {
        "sender": "USER",
        "recipient": "Zosia",
        "object": "book",
    }


def test_scope_safe_send_email_uses_world_index_for_unbound_recipient() -> None:
    task = _action_task(world_state={"entities": ["Zosia", "report"], "speaker": "USER"})
    contract = project_world_state_execution_contract(task, _send_world_analysis())
    assert contract["status"] == "READY"
    assert contract["tool"] == "send_email"
    assert contract["argument_bindings"] == {
        "document": "report",
        "recipient": "Zosia",
    }


def test_old_grounding_payload_cannot_override_validated_v02_world_bundle() -> None:
    analysis = _gives_world_analysis()
    poisoned = analysis["relation_entity_grounding"]["entries"][1]["grounding"]
    poisoned["status"] = "RESOLVED_SHARED_CARD_ID"
    poisoned["world_entity"] = "Mallory"
    task = _relation_task(world_state={"entities": ["Zosia", "book"], "speaker": "USER"})
    contract = project_world_state_execution_contract(task, analysis)
    assert contract["status"] == "READY"
    assert contract["argument_bindings"]["recipient"] == "Zosia"


def test_world_index_mutation_without_rehash_fails_continuity() -> None:
    analysis = _gives_world_analysis()
    analysis["world_state_index"]["records"][1]["canonical_id"] = "Mallory"
    contract = project_world_state_execution_contract(
        _relation_task(world_state={"entities": ["Zosia", "book"], "speaker": "USER"}),
        analysis,
    )
    assert contract["status"] == "AMBIGUOUS"
    assert contract["reason"] == "RELATION_WORLD_STATE_GROUNDING_CONTINUITY_FAIL"


def test_rehashed_grounding_bound_to_different_world_index_fails_continuity() -> None:
    analysis = _gives_world_analysis()
    grounding = analysis["relation_world_state_grounding"]
    grounding["world_state_index_commitment"] = "f" * 64
    body = {key: grounding[key] for key in (
        "schema",
        "equation_id",
        "language_id",
        "relation_hypergraph_commitment",
        "card_bindings_commitment",
        "world_state_index_commitment",
        "entries",
        "candidate_only",
    )}
    grounding["commitment"] = _sha256_json(body)
    issues = validate_world_grounding_payload(
        analysis["sentence_equation"],
        grounding,
        analysis["world_state_index"],
    )
    assert "relation world grounding world-state commitment mismatch" in issues


def test_rehashed_missing_entity_partition_fails_continuity() -> None:
    analysis = _gives_world_analysis()
    grounding = analysis["relation_world_state_grounding"]
    grounding["entries"] = grounding["entries"][:-1]
    body = {key: grounding[key] for key in (
        "schema",
        "equation_id",
        "language_id",
        "relation_hypergraph_commitment",
        "card_bindings_commitment",
        "world_state_index_commitment",
        "entries",
        "candidate_only",
    )}
    grounding["commitment"] = _sha256_json(body)
    issues = validate_world_grounding_payload(
        analysis["sentence_equation"],
        grounding,
        analysis["world_state_index"],
    )
    assert "relation world grounding entity partition mismatch" in issues


def test_unresolved_world_state_entity_remains_blocked() -> None:
    analysis = _gives_world_analysis()
    recipient = analysis["relation_world_state_grounding"]["entries"][1]
    recipient["resolution_status"] = "UNRESOLVED_WORLD_STATE"
    recipient["world_entity"] = None
    recipient["confidence"] = 0.0
    grounding = analysis["relation_world_state_grounding"]
    body = {key: grounding[key] for key in (
        "schema",
        "equation_id",
        "language_id",
        "relation_hypergraph_commitment",
        "card_bindings_commitment",
        "world_state_index_commitment",
        "entries",
        "candidate_only",
    )}
    grounding["commitment"] = _sha256_json(body)
    contract = project_world_state_execution_contract(
        _relation_task(world_state={"entities": ["Zosia", "book"], "speaker": "USER"}),
        analysis,
    )
    assert contract["status"] == "AMBIGUOUS"
    assert contract["reason"].startswith("WORLD_ENTITY_UNRESOLVED:recipient")


def test_receipt_does_not_depend_on_benchmark_ground_truth() -> None:
    world = {"entities": ["Zosia", "book"], "speaker": "USER"}
    execute = GroundTruth(
        Decision.EXECUTE,
        tool="transfer_object",
        arguments={"sender": "USER", "recipient": "Zosia", "object": "book"},
    )
    ask = GroundTruth(Decision.ASK, reason_code="MUTATED_FIXTURE")
    analysis = _gives_world_analysis()
    r1 = build_world_state_ciel_receipt(
        _relation_task(world_state=world, truth=execute),
        lambda _: deepcopy(analysis),
    )
    r2 = build_world_state_ciel_receipt(
        _relation_task(world_state=world, truth=ask),
        lambda _: deepcopy(analysis),
    )
    assert r1 == r2
    assert r1["ground_truth_used"] is False
