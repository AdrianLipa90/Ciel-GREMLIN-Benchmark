from __future__ import annotations

import json
from pathlib import Path

import pytest

from ciel_gremlin_benchmark.openai_live import (
    OpenAIResponsesAdapter,
    ReceiptBundleStore,
)
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
        task_id="F6-TEST",
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


def structured_response() -> dict:
    return {
        "id": "resp_test",
        "status": "completed",
        "model": "model-x",
        "output": [{
            "type": "function_call",
            "name": "submit_benchmark_decision",
            "arguments": json.dumps({
                "decision": "EXECUTE",
                "tool": "transfer_object",
                "arguments_json": json.dumps({
                    "sender": "USER",
                    "recipient": "Zosia",
                    "object": "book",
                }),
            }),
        }],
        "usage": {"input_tokens": 100, "output_tokens": 20},
    }


def test_b1_forces_strict_decision_function_and_parses_prediction() -> None:
    transport = FakeTransport(structured_response())
    adapter = OpenAIResponsesAdapter(
        system_id="B1",
        model_id="model-x",
        prompt="structured prompt",
        transport=transport,
        model_parameters={"temperature": 0},
    )
    prediction = adapter.predict(task())
    assert prediction.decision is Decision.EXECUTE
    assert prediction.tool == "transfer_object"
    assert prediction.arguments["recipient"] == "Zosia"
    assert prediction.cost.input_tokens == 100
    payload = transport.payloads[0]
    assert payload["tool_choice"] == {
        "type": "function",
        "name": "submit_benchmark_decision",
    }
    assert payload["parallel_tool_calls"] is False
    assert payload["tools"][0]["strict"] is True
    assert payload["tools"][0]["parameters"]["additionalProperties"] is False
    assert payload["store"] is False


def test_b0_has_no_schema_enforcement_and_parses_plain_json() -> None:
    transport = FakeTransport({
        "id": "resp_b0",
        "status": "completed",
        "model": "model-x",
        "output_text": json.dumps({
            "decision": "ASK",
            "tool": None,
            "arguments": {},
        }),
        "usage": {},
    })
    adapter = OpenAIResponsesAdapter(
        system_id="B0",
        model_id="model-x",
        prompt="direct prompt",
        transport=transport,
    )
    prediction = adapter.predict(task())
    assert prediction.decision is Decision.ASK
    payload = transport.payloads[0]
    assert "tools" not in payload
    assert "tool_choice" not in payload
    assert "structured_output" not in prediction.receipts


def test_b4_injects_gremlin_but_applies_ciel_gate_after_model(tmp_path: Path) -> None:
    bundle = tmp_path / "receipts.jsonl"
    bundle.write_text(json.dumps({
        "task_id": "F6-TEST",
        "gremlin": {"commitment": "g", "candidate_only": True},
        "ciel": {"commitment": "c", "validation": "PASS"},
        "execution_gate": {"commitment": "e", "action": "DEFER"},
    }) + "\n", encoding="utf-8")
    store = ReceiptBundleStore.from_jsonl(bundle)
    transport = FakeTransport(structured_response())
    adapter = OpenAIResponsesAdapter(
        system_id="B4",
        model_id="model-x",
        prompt="research prompt",
        transport=transport,
        receipt_store=store,
    )
    prediction = adapter.predict(task())
    assert prediction.decision is Decision.DEFER
    assert prediction.tool is None
    assert prediction.arguments == {}
    assert prediction.receipts["gremlin"]["commitment"] == "g"
    assert prediction.receipts["ciel"]["commitment"] == "c"
    assert prediction.receipts["execution_gate"]["action"] == "DEFER"
    request_input = json.loads(transport.payloads[0]["input"])
    assert request_input["gremlin_research_receipt"]["commitment"] == "g"
    assert "ciel" not in request_input
    assert "execution_gate" not in request_input


def test_missing_component_receipt_fails_before_network() -> None:
    transport = FakeTransport(structured_response())
    adapter = OpenAIResponsesAdapter(
        system_id="B3",
        model_id="model-x",
        prompt="structured prompt",
        transport=transport,
    )
    with pytest.raises(ValueError, match="requires CIEL receipt"):
        adapter.predict(task())
    assert transport.payloads == []


def test_receipt_store_rejects_duplicate_task_ids(tmp_path: Path) -> None:
    path = tmp_path / "dup.jsonl"
    row = json.dumps({"task_id": "F6-TEST", "gremlin": {"x": 1}})
    path.write_text(row + "\n" + row + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate task_id"):
        ReceiptBundleStore.from_jsonl(path)


def test_unknown_model_parameter_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported Responses API model parameters"):
        OpenAIResponsesAdapter(
            system_id="B1",
            model_id="model-x",
            prompt="p",
            transport=FakeTransport(structured_response()),
            model_parameters={"seed": 7},
        )
