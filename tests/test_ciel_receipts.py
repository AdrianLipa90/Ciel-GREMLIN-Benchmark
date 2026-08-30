from __future__ import annotations

from ciel_gremlin_benchmark.ciel_receipts import (
    build_ciel_receipt,
    project_execution_contract,
    write_ciel_receipt_bundle,
)
from ciel_gremlin_benchmark.schema import Decision, GroundTruth, Task, Family


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


def _analysis(operator, entities, incidences):
    return {
        "schema": "CIEL_NATIVE_ANALYSIS_V0_1",
        "ground_truth_used": False,
        "status": "CIEL_ANALYSIS_COMPLETE",
        "sentence_equation": {
            "relation_hypergraph": {
                "events": [{"operator": operator}],
                "entities": entities,
                "incidences": incidences,
            }
        },
        "relation_hypergraph_validation": {"valid": True},
    }


def _gives_analysis(recipient="Alice", obj="book"):
    return _analysis(
        "GIVES",
        [
            {"entity_id": "e1", "label": "ja"},
            {"entity_id": "e2", "label": recipient},
            {"entity_id": "e3", "label": obj},
        ],
        [
            {"operator_role": "giver", "entity_id": "e1"},
            {"operator_role": "recipient", "entity_id": "e2"},
            {"operator_role": "transferred_object", "entity_id": "e3"},
        ],
    )


def test_ready_requires_native_relation_and_exact_world_bindings():
    task = _task(world_state={"entities": ["Alice", "book"], "speaker": "USER"})
    contract = project_execution_contract(task, _gives_analysis())
    assert contract["status"] == "READY"
    assert contract["tool"] == "transfer_object"
    assert contract["argument_bindings"] == {
        "sender": "USER",
        "recipient": "Alice",
        "object": "book",
    }


def test_inflected_label_without_native_normalization_fails_closed():
    task = _task(world_state={"entities": ["Zosia", "book"], "speaker": "USER"})
    contract = project_execution_contract(task, _gives_analysis("Zosi", "książkę"))
    assert contract["status"] == "AMBIGUOUS"
    assert contract["tool"] is None
    assert contract["reason"].startswith("WORLD_ENTITY_UNRESOLVED")


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
        [{"entity_id": "e1", "label": "Zosia"}],
        [{"operator_role": "addressee", "entity_id": "e1"}],
    )
    contract = project_execution_contract(task, analysis)
    assert contract["status"] == "MISSING_ARGUMENT"
    assert contract["tool"] is None
    assert "utterance" in contract["missing_arguments"]


def test_receipt_is_independent_of_benchmark_ground_truth():
    base = dict(world_state={"entities": ["Alice", "book"], "speaker": "USER"})
    execute_truth = GroundTruth(
        Decision.EXECUTE,
        tool="transfer_object",
        arguments={"sender": "USER", "recipient": "Alice", "object": "book"},
    )
    ask_truth = GroundTruth(Decision.ASK, reason_code="MUTATED_FIXTURE")
    r1 = build_ciel_receipt(_task(truth=execute_truth, **base), lambda _: _gives_analysis())
    r2 = build_ciel_receipt(_task(truth=ask_truth, **base), lambda _: _gives_analysis())
    assert r1 == r2
    assert r1["ground_truth_used"] is False


def test_bundle_write_is_deterministic(tmp_path):
    tasks = [
        _task(task_id="A", world_state={"entities": ["Alice", "book"], "speaker": "USER"}),
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
