from __future__ import annotations

from copy import deepcopy

from ciel_gremlin_benchmark import ciel_action_scope as scoped
from ciel_gremlin_benchmark.schema import Decision, Family, GroundTruth, Task


_GRAPH_SHA = "a" * 64
_CARD_SHA = "b" * 64


def _task(*, task_id="T", allowed_tools=("send_email",), truth=None, world_state=None):
    return Task(
        task_id=task_id,
        family=Family.F2_OBJECT_ACTION,
        language="pl",
        user_input="fixture",
        world_state=world_state or {},
        evidence=(),
        allowed_tools=tuple(allowed_tools),
        ground_truth=truth or GroundTruth(Decision.ASK, reason_code="FIXTURE"),
    )


def _resolved(entity_id, world_entity, *, card_id=None):
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


def _implicit(entity_id, world_entity="USER"):
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


def _scope_gate(*, status="SCOPE_SAFE", safe=True, reason=None):
    reason = reason or (
        "SCOPE_SAFE_EXACT_AGREEMENT" if safe else f"BLOCK_{status}"
    )
    body = {
        "schema": scoped.ACTION_SCOPE_GATE_SCHEMA,
        "producer_present": True,
        "producer_valid": True,
        "recomputation_match": True,
        "producer_status": status,
        "recomputed_status": status,
        "safe_for_tool_projection": safe,
        "reason": reason,
        "surface_commitment": "d" * 64,
        "producer_commitment": "e" * 64,
        "basis": "INDEPENDENT_SCOPE_RECOMPUTATION_V0_1",
        "candidate_only": True,
    }
    return {**body, "commitment": scoped._sha256_json(body)}


def _analysis(operator, entities, incidences, grounding_entries, *, gate=None):
    equation = {
        "equation_id": "eq-action",
        "language_id": "pl",
        "tokens": ["fixture"],
        "relation_hypergraph": {
            "commitment": _GRAPH_SHA,
            "events": [{"operator": operator}],
            "entities": entities,
            "incidences": incidences,
        },
        "relation_entity_card_bindings": {"commitment": _CARD_SHA},
    }
    return {
        "schema": "CIEL_NATIVE_ANALYSIS_V0_1",
        "ground_truth_used": False,
        "status": "CIEL_ANALYSIS_COMPLETE",
        "sentence_equation": equation,
        "relation_hypergraph_validation": {"valid": True},
        "relation_entity_grounding": {
            "schema": scoped.base.GROUNDING_SCHEMA,
            "equation_id": "eq-action",
            "language_id": "pl",
            "relation_hypergraph_commitment": _GRAPH_SHA,
            "card_bindings_commitment": _CARD_SHA,
            "entries": grounding_entries,
            "candidate_only": True,
            "commitment": "c" * 64,
        },
        "action_scope_gate": gate or _scope_gate(),
    }


def _send_email_analysis(*, gate=None, recipient_resolved=True):
    entries = [
        _implicit("actor"),
        _resolved("doc", "report", card_id="concept:report"),
        _resolved("recipient", "Zosia", card_id="concept:person:zosia"),
    ]
    if not recipient_resolved:
        entries[2] = {
            "entity_id": "recipient",
            "source_status": "UNBOUND",
            "binding_id": None,
            "card_id": None,
            "grounding": {"status": "UNRESOLVED", "world_entity": None},
            "candidate_only": True,
        }
    return _analysis(
        "SEND_EMAIL",
        [
            {"entity_id": "actor", "label": "ja"},
            {"entity_id": "doc", "label": "raport"},
            {"entity_id": "recipient", "label": "Zosi"},
        ],
        [
            {"operator_role": "sender", "entity_id": "actor"},
            {"operator_role": "document", "entity_id": "doc"},
            {"operator_role": "recipient", "entity_id": "recipient"},
        ],
        entries,
        gate=gate,
    )


def test_scope_safe_send_email_projects_ready_contract():
    contract = scoped.project_scoped_execution_contract(
        _task(world_state={"entities": ["Zosia", "report"]}),
        _send_email_analysis(),
    )
    assert contract["status"] == "READY"
    assert contract["tool"] == "send_email"
    assert contract["argument_bindings"] == {
        "document": "report",
        "recipient": "Zosia",
    }
    assert contract["reason"] == "CIEL_SCOPE_SAFE_ACTION_AND_SEMANTIC_GROUNDING_COMPLETE"


def test_negated_send_email_is_policy_reject_with_no_tool():
    contract = scoped.project_scoped_execution_contract(
        _task(),
        _send_email_analysis(gate=_scope_gate(status="NEGATED", safe=False)),
    )
    assert contract["status"] == "POLICY_REJECT"
    assert contract["tool"] is None
    assert contract["reason"] == "ACTION_SCOPE_NEGATED"


def test_corrupted_scope_gate_fails_closed_before_action_projection():
    gate = _scope_gate()
    gate["commitment"] = "f" * 64
    contract = scoped.project_scoped_execution_contract(
        _task(),
        _send_email_analysis(gate=gate),
    )
    assert contract["status"] == "AMBIGUOUS"
    assert contract["tool"] is None
    assert contract["reason"] == "ACTION_SCOPE_GATE_INVALID"


def test_scope_safe_update_record_projects_required_arguments():
    analysis = _analysis(
        "UPDATES_RECORD",
        [
            {"entity_id": "actor", "label": "ja"},
            {"entity_id": "record", "label": "44"},
            {"entity_id": "field", "label": "status"},
            {"entity_id": "value", "label": "approved"},
        ],
        [
            {"operator_role": "actor", "entity_id": "actor"},
            {"operator_role": "record", "entity_id": "record"},
            {"operator_role": "field", "entity_id": "field"},
            {"operator_role": "value", "entity_id": "value"},
        ],
        [
            _implicit("actor"),
            _resolved("record", "44", card_id="concept:record:44"),
            _resolved("field", "status", card_id="concept:field:status"),
            _resolved("value", "approved", card_id="concept:value:approved"),
        ],
    )
    contract = scoped.project_scoped_execution_contract(
        _task(allowed_tools=("update_record",)),
        analysis,
    )
    assert contract["status"] == "READY"
    assert contract["tool"] == "update_record"
    assert contract["argument_bindings"] == {
        "entity": "44",
        "field": "status",
        "value": "approved",
    }


def test_scope_safe_action_with_unresolved_recipient_stays_ambiguous():
    contract = scoped.project_scoped_execution_contract(
        _task(),
        _send_email_analysis(recipient_resolved=False),
    )
    assert contract["status"] == "AMBIGUOUS"
    assert contract["tool"] is None
    assert contract["reason"].startswith("WORLD_ENTITY_UNRESOLVED:recipient")


def test_legacy_operator_delegates_to_existing_projection(monkeypatch):
    sentinel = {
        "schema": scoped.base.CIEL_EXECUTION_CONTRACT_SCHEMA,
        "status": "READY",
        "tool": "transfer_object",
        "required_arguments": [],
        "argument_bindings": {},
        "allow_extra_arguments": False,
        "reason": "LEGACY_SENTINEL",
    }
    monkeypatch.setattr(scoped.base, "project_execution_contract", lambda task, analysis: sentinel)
    analysis = _analysis(
        "GIVES",
        [{"entity_id": "x", "label": "x"}],
        [],
        [],
    )
    assert scoped.project_scoped_execution_contract(_task(), analysis) is sentinel


def test_scoped_receipt_is_independent_of_benchmark_ground_truth():
    execute_truth = GroundTruth(
        Decision.EXECUTE,
        tool="send_email",
        arguments={"document": "report", "recipient": "Zosia"},
    )
    ask_truth = GroundTruth(Decision.ASK, reason_code="MUTATED_TRUTH")
    analyzer = lambda _: _send_email_analysis()
    first = scoped.build_scoped_ciel_receipt(
        _task(task_id="same", truth=execute_truth), analyzer
    )
    second = scoped.build_scoped_ciel_receipt(
        _task(task_id="same", truth=ask_truth), analyzer
    )
    assert first == second
    assert first["ground_truth_used"] is False


def test_scoped_bundle_write_is_deterministic(tmp_path):
    tasks = [_task(task_id="A"), _task(task_id="B")]
    analyzer = lambda _: _send_email_analysis()
    first = scoped.write_scoped_ciel_receipt_bundle(
        tasks, tmp_path / "a.jsonl", analyzer
    )
    second = scoped.write_scoped_ciel_receipt_bundle(
        tasks, tmp_path / "b.jsonl", analyzer
    )
    assert first["task_count"] == 2
    assert first["sha256"] == second["sha256"]
    assert (tmp_path / "a.jsonl").read_bytes() == (tmp_path / "b.jsonl").read_bytes()


def test_scope_gate_payload_rejects_rehashed_unsafe_allow_state():
    gate = _scope_gate(status="NEGATED", safe=False)
    forged = deepcopy(gate)
    forged["safe_for_tool_projection"] = True
    body = scoped._scope_gate_body(forged)
    forged["commitment"] = scoped._sha256_json(body)
    issues = scoped.validate_scope_gate_payload(forged)
    assert "action_scope_gate unsafe ALLOW state" in issues
