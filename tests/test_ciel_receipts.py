from __future__ import annotations

from ciel_gremlin_benchmark.ciel_receipts import (
    GROUNDING_SCHEMA,
    build_ciel_receipt,
    project_execution_contract,
    write_ciel_receipt_bundle,
)
from ciel_gremlin_benchmark.schema import Decision, GroundTruth, Task, Family


_GRAPH_SHA = "a" * 64
_CARD_SHA = "b" * 64


def _task(*, task_id="T", language="pl", world_state=None, allowed_tools=("transfer_object",), truth=None):
    return Task(
        task_id=task_id,
        family=Family.F6_NARY_RELATION,
        language=language,
        user_input="fixture",
        world_state=world_state or {},
        evidence=(),
        allowed_tools=tuple(allowed_tools),
        ground_truth=truth or GroundTruth(Decision.ASK, reason_code="FIXTURE"),
    )


def _resolved_entry(entity_id, world_entity, *, implicit=False, card_id=None):
    if implicit:
        return {
            "entity_id": entity_id,
            "source_status": "IMPLICIT",
            "binding_id": None,
            "card_id": None,
            "grounding": {
                "status": "RESOLVED_IMPLICIT_SPEAKER",
                "world_entity": world_entity,
            },
            "candidate_only": True,
        }
    card_id = card_id or f"concept:{world_entity.casefold()}"
    return {
        "entity_id": entity_id,
        "source_status": "BOUND",
        "binding_id": f"bind:{entity_id}",
        "card_id": card_id,
        "grounding": {
            "status": "RESOLVED_SHARED_CARD_ID",
            "world_entity": world_entity,
            "card_id": card_id,
        },
        "candidate_only": True,
    }


def _unresolved_entry(entity_id, *, source_status="UNBOUND"):
    return {
        "entity_id": entity_id,
        "source_status": source_status,
        "binding_id": None,
        "card_id": None,
        "grounding": {
            "status": "UNRESOLVED",
            "world_entity": None,
        },
        "candidate_only": True,
    }


def _analysis(operator, entities, incidences, *, grounding_entries=None, graph_sha=_GRAPH_SHA):
    equation = {
        "equation_id": "eq-fixture",
        "language_id": "pl",
        "relation_hypergraph": {
            "commitment": graph_sha,
            "events": [{"operator": operator}],
            "entities": entities,
            "incidences": incidences,
        },
        "relation_entity_card_bindings": {
            "commitment": _CARD_SHA,
        },
    }
    analysis = {
        "schema": "CIEL_NATIVE_ANALYSIS_V0_1",
        "ground_truth_used": False,
        "status": "CIEL_ANALYSIS_COMPLETE",
        "sentence_equation": equation,
        "relation_hypergraph_validation": {"valid": True},
    }
    if grounding_entries is not None:
        analysis["relation_entity_grounding"] = {
            "schema": GROUNDING_SCHEMA,
            "equation_id": "eq-fixture",
            "language_id": "pl",
            "relation_hypergraph_commitment": graph_sha,
            "card_bindings_commitment": _CARD_SHA,
            "entries": grounding_entries,
            "candidate_only": True,
            "commitment": "c" * 64,
        }
    return analysis


def _gives_analysis(*, resolved=True):
    entries = [
        _resolved_entry("e1", "USER", implicit=True),
        _resolved_entry("e2", "Zosia", card_id="concept:person:zosia"),
        _resolved_entry("e3", "book", card_id="concept:book"),
    ]
    if not resolved:
        entries[1] = _unresolved_entry("e2")
    return _analysis(
        "GIVES",
        [
            {"entity_id": "e1", "label": "ja"},
            {"entity_id": "e2", "label": "Zosi"},
            {"entity_id": "e3", "label": "książkę"},
        ],
        [
            {"operator_role": "giver", "entity_id": "e1"},
            {"operator_role": "recipient", "entity_id": "e2"},
            {"operator_role": "transferred_object", "entity_id": "e3"},
        ],
        grounding_entries=entries,
    )


def test_ready_uses_semantic_grounding_not_surface_spelling():
    task = _task(world_state={"entities": ["Zosia", "book"], "speaker": "USER"})
    contract = project_execution_contract(task, _gives_analysis())
    assert contract["status"] == "READY"
    assert contract["tool"] == "transfer_object"
    assert contract["argument_bindings"] == {
        "sender": "USER",
        "recipient": "Zosia",
        "object": "book",
    }
    assert contract["reason"] == "CIEL_TYPED_RELATION_AND_SEMANTIC_GROUNDING_COMPLETE"


def test_surface_match_without_semantic_grounding_fails_closed():
    task = _task(world_state={"entities": ["Alice", "book"], "speaker": "USER"})
    analysis = _analysis(
        "GIVES",
        [
            {"entity_id": "e1", "label": "ja"},
            {"entity_id": "e2", "label": "Alice"},
            {"entity_id": "e3", "label": "book"},
        ],
        [
            {"operator_role": "giver", "entity_id": "e1"},
            {"operator_role": "recipient", "entity_id": "e2"},
            {"operator_role": "transferred_object", "entity_id": "e3"},
        ],
    )
    contract = project_execution_contract(task, analysis)
    assert contract["status"] == "AMBIGUOUS"
    assert contract["reason"] == "RELATION_ENTITY_GROUNDING_ABSENT"


def test_unresolved_semantic_identity_fails_closed_even_when_surface_could_be_guessed():
    task = _task(world_state={"entities": ["Zosia", "book"], "speaker": "USER"})
    contract = project_execution_contract(task, _gives_analysis(resolved=False))
    assert contract["status"] == "AMBIGUOUS"
    assert contract["tool"] is None
    assert contract["reason"].startswith("WORLD_ENTITY_UNRESOLVED:recipient")


def test_grounding_bundle_must_match_exact_hypergraph_commitment():
    analysis = _gives_analysis()
    analysis["relation_entity_grounding"]["relation_hypergraph_commitment"] = "d" * 64
    contract = project_execution_contract(
        _task(world_state={"entities": ["Zosia", "book"], "speaker": "USER"}),
        analysis,
    )
    assert contract["status"] == "AMBIGUOUS"
    assert contract["reason"] == "RELATION_ENTITY_GROUNDING_CONTINUITY_FAIL"


def test_unsupported_language_is_ambiguous_not_guessed():
    task = _task(language="en", world_state={"entities": ["node-A", "node-B"]}, allowed_tools=("record_relation",))
    contract = project_execution_contract(
        task,
        {"ground_truth_used": False, "status": "LANGUAGE_UNSUPPORTED_BY_PINNED_CIEL"},
    )
    assert contract["status"] == "AMBIGUOUS"
    assert contract["tool"] is None


def test_missing_semantic_argument_stays_missing_argument():
    task = _task(world_state={"entities": ["Zosia"]}, allowed_tools=("address_person",))
    analysis = _analysis(
        "ADDRESSES",
        [{"entity_id": "e1", "label": "Zosiu"}],
        [{"operator_role": "addressee", "entity_id": "e1"}],
        grounding_entries=[_resolved_entry("e1", "Zosia", card_id="concept:person:zosia")],
    )
    contract = project_execution_contract(task, analysis)
    assert contract["status"] == "MISSING_ARGUMENT"
    assert contract["tool"] is None
    assert "utterance" in contract["missing_arguments"]


def test_receipt_is_independent_of_benchmark_ground_truth():
    base = dict(world_state={"entities": ["Zosia", "book"], "speaker": "USER"})
    execute_truth = GroundTruth(
        Decision.EXECUTE,
        tool="transfer_object",
        arguments={"sender": "USER", "recipient": "Zosia", "object": "book"},
    )
    ask_truth = GroundTruth(Decision.ASK, reason_code="MUTATED_FIXTURE")
    r1 = build_ciel_receipt(_task(truth=execute_truth, **base), lambda _: _gives_analysis())
    r2 = build_ciel_receipt(_task(truth=ask_truth, **base), lambda _: _gives_analysis())
    assert r1 == r2
    assert r1["ground_truth_used"] is False


def test_bundle_write_is_deterministic(tmp_path):
    tasks = [
        _task(task_id="A", world_state={"entities": ["Zosia", "book"], "speaker": "USER"}),
        _task(task_id="B", language="en", allowed_tools=("record_relation",)),
    ]

    def analyzer(task):
        if task.language == "pl":
            return _gives_analysis()
        return {"ground_truth_used": False, "status": "LANGUAGE_UNSUPPORTED_BY_PINNED_CIEL"}

    a = write_ciel_receipt_bundle(tasks, tmp_path / "a.jsonl", analyzer)
    b = write_ciel_receipt_bundle(tasks, tmp_path / "b.jsonl", analyzer)
    assert a["task_count"] == 2
    assert a["sha256"] == b["sha256"]
    assert (tmp_path / "a.jsonl").read_bytes() == (tmp_path / "b.jsonl").read_bytes()
