from __future__ import annotations

import json
from pathlib import Path

import pytest

from ciel_gremlin_benchmark.dynamic_gate import (
    CIEL_EXECUTION_CONTRACT_SCHEMA,
    DynamicCIELExecutionGate,
    execution_contract_sha256,
)
from ciel_gremlin_benchmark.dynamic_live import DynamicOpenAIResponsesAdapter
from ciel_gremlin_benchmark.openai_live import ReceiptBundleStore
from ciel_gremlin_benchmark.schema import Decision, Family, GroundTruth, Task


class FakeTransport:
    def __init__(self, response: dict):
        self.response = response
        self.payloads: list[dict] = []

    def create_response(self, payload):
        self.payloads.append(dict(payload))
        return self.response


def task() -> Task:
    return Task(
        task_id="F6-DYNAMIC",
        family=Family.F6_NARY_RELATION,
        language="pl",
        user_input="Daj Zosi książkę.",
        world_state={"speaker": "USER"},
        evidence=(),
        allowed_tools=("transfer_object",),
        ground_truth=GroundTruth(
            decision=Decision.EXECUTE,
            tool="transfer_object",
            arguments={"sender": "USER", "recipient": "Zosia", "object": "book"},
        ),
    )


def ciel_receipt(status: str = "READY") -> dict:
    contract = {
        "schema": CIEL_EXECUTION_CONTRACT_SCHEMA,
        "status": status,
        "tool": "transfer_object" if status == "READY" else None,
        "required_arguments": ["sender", "recipient", "object"] if status == "READY" else [],
        "argument_bindings": (
            {"sender": "USER", "recipient": "Zosia", "object": "book"}
            if status == "READY"
            else {}
        ),
        "allow_extra_arguments": False,
    }
    return {
        "candidate_only": True,
        "ground_truth_used": False,
        "source_commitment": "a" * 64,
        "execution_contract": contract,
        "execution_contract_sha256": execution_contract_sha256(contract),
    }


def structured_response(*, decision="EXECUTE", tool="transfer_object", arguments=None) -> dict:
    if arguments is None:
        arguments = {"sender": "USER", "recipient": "Zosia", "object": "book"}
    return {
        "id": "resp_dynamic",
        "status": "completed",
        "model": "model-x",
        "output": [{
            "type": "function_call",
            "name": "submit_benchmark_decision",
            "arguments": json.dumps({
                "decision": decision,
                "tool": tool or "",
                "arguments_json": json.dumps(arguments),
            }),
        }],
        "usage": {"input_tokens": 50, "output_tokens": 10},
    }


def write_bundle(path: Path, *, ciel: dict, gremlin=None, execution_gate=None) -> ReceiptBundleStore:
    row = {"task_id": "F6-DYNAMIC", "ciel": ciel}
    if gremlin is not None:
        row["gremlin"] = gremlin
    if execution_gate is not None:
        row["execution_gate"] = execution_gate
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return ReceiptBundleStore.from_jsonl(path)


def test_valid_model_proposal_is_allowed_without_repair(tmp_path: Path) -> None:
    transport = FakeTransport(structured_response())
    store = write_bundle(tmp_path / "r.jsonl", ciel=ciel_receipt())
    prediction = DynamicOpenAIResponsesAdapter(
        system_id="B3", model_id="model-x", prompt="p", transport=transport, receipt_store=store
    ).predict(task())
    assert prediction.decision is Decision.EXECUTE
    assert prediction.arguments["recipient"] == "Zosia"
    gate = prediction.receipts["execution_gate"]
    assert gate["action"] == "ALLOW"
    assert gate["ground_truth_used"] is False
    assert gate["proposal_sha256"] == prediction.diagnostics["pre_gate_proposal_sha256"]


def test_wrong_recipient_is_rejected_after_model_proposal(tmp_path: Path) -> None:
    transport = FakeTransport(structured_response(arguments={
        "sender": "USER", "recipient": "Alicja", "object": "book"
    }))
    store = write_bundle(tmp_path / "r.jsonl", ciel=ciel_receipt())
    prediction = DynamicOpenAIResponsesAdapter(
        system_id="B3", model_id="model-x", prompt="p", transport=transport, receipt_store=store
    ).predict(task())
    assert prediction.decision is Decision.REJECT
    assert prediction.tool is None
    assert prediction.arguments == {}
    assert prediction.receipts["execution_gate"]["reasons"] == ["ARGUMENT_BINDING_MISMATCH"]


def test_missing_required_argument_becomes_ask_not_repaired(tmp_path: Path) -> None:
    transport = FakeTransport(structured_response(arguments={"sender": "USER", "recipient": "Zosia"}))
    store = write_bundle(tmp_path / "r.jsonl", ciel=ciel_receipt())
    prediction = DynamicOpenAIResponsesAdapter(
        system_id="B3", model_id="model-x", prompt="p", transport=transport, receipt_store=store
    ).predict(task())
    assert prediction.decision is Decision.ASK
    assert prediction.arguments == {}
    assert prediction.receipts["execution_gate"]["reasons"] == ["MISSING_REQUIRED_ARGUMENT"]


def test_missing_evidence_contract_blocks_execute_with_defer(tmp_path: Path) -> None:
    transport = FakeTransport(structured_response())
    store = write_bundle(tmp_path / "r.jsonl", ciel=ciel_receipt("MISSING_EVIDENCE"))
    prediction = DynamicOpenAIResponsesAdapter(
        system_id="B3", model_id="model-x", prompt="p", transport=transport, receipt_store=store
    ).predict(task())
    assert prediction.decision is Decision.DEFER
    assert prediction.receipts["execution_gate"]["action"] == "DEFER"


def test_conservative_model_nonexecution_is_never_promoted_to_execute(tmp_path: Path) -> None:
    transport = FakeTransport(structured_response(decision="ASK", tool=None, arguments={}))
    store = write_bundle(tmp_path / "r.jsonl", ciel=ciel_receipt())
    prediction = DynamicOpenAIResponsesAdapter(
        system_id="B3", model_id="model-x", prompt="p", transport=transport, receipt_store=store
    ).predict(task())
    assert prediction.decision is Decision.ASK
    assert prediction.receipts["execution_gate"]["action"] == "ALLOW"
    assert prediction.receipts["execution_gate"]["reasons"] == ["CONSERVATIVE_NON_EXECUTION_PRESERVED"]


def test_precomputed_gate_is_rejected_before_network(tmp_path: Path) -> None:
    transport = FakeTransport(structured_response())
    store = write_bundle(
        tmp_path / "r.jsonl",
        ciel=ciel_receipt(),
        execution_gate={"action": "ALLOW", "commitment": "oracle-like-static-action"},
    )
    adapter = DynamicOpenAIResponsesAdapter(
        system_id="B3", model_id="model-x", prompt="p", transport=transport, receipt_store=store
    )
    with pytest.raises(ValueError, match="precomputed execution_gate is forbidden"):
        adapter.predict(task())
    assert transport.payloads == []


def test_tampered_ciel_contract_fails_before_network(tmp_path: Path) -> None:
    receipt = ciel_receipt()
    receipt["execution_contract"]["argument_bindings"]["recipient"] = "Alicja"
    transport = FakeTransport(structured_response())
    store = write_bundle(tmp_path / "r.jsonl", ciel=receipt)
    adapter = DynamicOpenAIResponsesAdapter(
        system_id="B3", model_id="model-x", prompt="p", transport=transport, receipt_store=store
    )
    with pytest.raises(ValueError, match="commitment mismatch"):
        adapter.predict(task())
    assert transport.payloads == []


def test_receipt_must_explicitly_disclaim_ground_truth_use(tmp_path: Path) -> None:
    receipt = ciel_receipt()
    del receipt["ground_truth_used"]
    transport = FakeTransport(structured_response())
    store = write_bundle(tmp_path / "r.jsonl", ciel=receipt)
    adapter = DynamicOpenAIResponsesAdapter(
        system_id="B3", model_id="model-x", prompt="p", transport=transport, receipt_store=store
    )
    with pytest.raises(ValueError, match="ground_truth_used=false"):
        adapter.predict(task())
    assert transport.payloads == []


def test_ready_contract_tool_must_exist_in_allowed_tools() -> None:
    receipt = ciel_receipt()
    receipt["execution_contract"]["tool"] = "delete_file"
    receipt["execution_contract_sha256"] = execution_contract_sha256(receipt["execution_contract"])
    with pytest.raises(ValueError, match="not admitted by task.allowed_tools"):
        DynamicCIELExecutionGate().evaluate(
            task(), Decision.EXECUTE, "delete_file", {"sender": "USER"}, receipt
        )


def test_b4_gremlin_is_pre_model_but_ciel_is_post_model_only(tmp_path: Path) -> None:
    transport = FakeTransport(structured_response())
    store = write_bundle(
        tmp_path / "r.jsonl",
        ciel=ciel_receipt(),
        gremlin={"schema": "GREMLIN_RESEARCH_EXECUTOR_V0_1", "status": "NO_EVIDENCE_FAIL_CLOSED"},
    )
    prediction = DynamicOpenAIResponsesAdapter(
        system_id="B4", model_id="model-x", prompt="p", transport=transport, receipt_store=store
    ).predict(task())
    request_input = json.loads(transport.payloads[0]["input"])
    assert "gremlin_research_receipt" in request_input
    assert "ciel" not in request_input
    assert "execution_gate" not in request_input
    assert prediction.receipts["execution_gate"]["action"] == "ALLOW"


def test_gate_does_not_consult_task_ground_truth() -> None:
    gate = DynamicCIELExecutionGate()
    base = task()
    changed_truth = Task(
        task_id=base.task_id,
        family=base.family,
        language=base.language,
        user_input=base.user_input,
        world_state=base.world_state,
        evidence=base.evidence,
        allowed_tools=base.allowed_tools,
        ground_truth=GroundTruth(decision=Decision.REJECT),
    )
    receipt = ciel_receipt()
    proposal = {"sender": "USER", "recipient": "Zosia", "object": "book"}
    a = gate.evaluate(base, Decision.EXECUTE, "transfer_object", proposal, receipt)
    b = gate.evaluate(changed_truth, Decision.EXECUTE, "transfer_object", proposal, receipt)
    assert a == b
