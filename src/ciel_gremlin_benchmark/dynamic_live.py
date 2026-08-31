from __future__ import annotations

from typing import Any, Mapping
import time

from .dynamic_gate import DynamicCIELExecutionGate, proposal_sha256, validate_ciel_receipt
from .openai_live import (
    OPENAI_RESPONSES_URL,
    ReceiptBundle,
    ReceiptBundleStore,
    ResponsesTransport,
    UrllibOpenAIResponsesTransport,
    _apply_execution_gate,
    _canonical_json,
    _decision_tool,
    _parse_structured_decision,
    _parse_unstructured_decision,
    _sha256_json,
    _task_payload,
)
from .schema import Cost, Prediction, Task
from .systems import get_system_contract


class DynamicOpenAIResponsesAdapter:
    """B0-B4 live adapter with a proposal-bound CIEL execution gate.

    GREMLIN remains pre-model context for B2/B4. CIEL remains hidden from the
    model and is evaluated only after the model emits a concrete proposal. A
    precomputed execution-gate action is rejected as benchmark leakage.
    """

    def __init__(
        self,
        *,
        system_id: str,
        model_id: str,
        prompt: str,
        transport: ResponsesTransport,
        model_parameters: Mapping[str, Any] | None = None,
        receipt_store: ReceiptBundleStore | None = None,
        ciel_gate: DynamicCIELExecutionGate | None = None,
    ) -> None:
        self.system_id = system_id
        self.contract = get_system_contract(system_id)
        self.model_id = str(model_id)
        self.prompt = str(prompt)
        self.transport = transport
        self.receipt_store = receipt_store
        self.ciel_gate = ciel_gate or DynamicCIELExecutionGate()
        self.model_parameters = dict(model_parameters or {})

        # Keep parameter admission byte-for-byte aligned with the legacy adapter
        # without depending on a private module constant.
        allowed = {"temperature", "top_p", "max_output_tokens", "reasoning", "service_tier"}
        unknown = set(self.model_parameters) - allowed
        if unknown:
            raise ValueError(f"unsupported Responses API model parameters: {sorted(unknown)}")

    def _receipts_for_task(self, task: Task) -> ReceiptBundle:
        bundle = self.receipt_store.get(task.task_id) if self.receipt_store else None
        if bundle is None:
            bundle = ReceiptBundle(task_id=task.task_id)
        if self.contract.gremlin and bundle.gremlin is None:
            raise ValueError(f"{task.task_id}: {self.system_id} requires GREMLIN receipt")
        if self.contract.ciel:
            if bundle.ciel is None:
                raise ValueError(f"{task.task_id}: {self.system_id} requires CIEL receipt")
            issues = validate_ciel_receipt(bundle.ciel)
            if issues:
                raise ValueError(f"{task.task_id}: invalid CIEL receipt: " + "; ".join(issues))
        if self.contract.execution_gate and bundle.execution_gate is not None:
            raise ValueError(
                f"{task.task_id}: precomputed execution_gate is forbidden in dynamic-gate mode"
            )
        return bundle

    def _request_payload(self, task: Task, bundle: ReceiptBundle) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model_id,
            "instructions": self.prompt,
            "input": _canonical_json(
                _task_payload(
                    task,
                    gremlin=bundle.gremlin if self.contract.gremlin else None,
                )
            ),
            "store": False,
        }
        payload.update(self.model_parameters)
        if self.contract.structured_output:
            payload.update({
                "tools": [_decision_tool(task)],
                "tool_choice": {"type": "function", "name": "submit_benchmark_decision"},
                "parallel_tool_calls": False,
            })
        return payload

    def predict(self, task: Task) -> Prediction:
        bundle = self._receipts_for_task(task)
        request_payload = self._request_payload(task, bundle)
        started = time.perf_counter()
        response = self.transport.create_response(request_payload)
        latency_ms = (time.perf_counter() - started) * 1000.0

        if str(response.get("status", "completed")) not in {"completed", ""}:
            raise RuntimeError(f"Responses API returned status={response.get('status')!r}")

        if self.contract.structured_output:
            decision, tool, arguments = _parse_structured_decision(response)
        else:
            decision, tool, arguments = _parse_unstructured_decision(response)

        pre_gate_sha = proposal_sha256(decision, tool, arguments)
        dynamic_gate_receipt: dict[str, Any] | None = None
        if self.contract.execution_gate:
            assert bundle.ciel is not None
            dynamic_gate_receipt = self.ciel_gate.evaluate(
                task,
                decision,
                tool,
                arguments,
                bundle.ciel,
            )
            if dynamic_gate_receipt.get("proposal_sha256") != pre_gate_sha:
                raise ValueError("dynamic gate proposal commitment mismatch")
            decision, tool, arguments = _apply_execution_gate(
                decision,
                tool,
                arguments,
                dynamic_gate_receipt,
            )

        usage = response.get("usage") if isinstance(response.get("usage"), Mapping) else {}
        input_tokens = int(usage.get("input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)

        receipts: dict[str, Any] = {}
        if self.contract.structured_output:
            receipts["structured_output"] = {
                "provider": "openai",
                "api": "responses",
                "response_id": response.get("id"),
                "model": response.get("model", self.model_id),
                "request_sha256": _sha256_json(request_payload),
                "strict_function": "submit_benchmark_decision",
            }
        if self.contract.gremlin:
            receipts["gremlin"] = dict(bundle.gremlin or {})
        if self.contract.ciel:
            receipts["ciel"] = dict(bundle.ciel or {})
        if self.contract.execution_gate:
            receipts["execution_gate"] = dict(dynamic_gate_receipt or {})

        return Prediction(
            system_id=self.system_id,
            task_id=task.task_id,
            decision=decision,
            tool=tool,
            arguments=arguments,
            diagnostics={
                "provider": "openai",
                "api": "responses",
                "response_id": response.get("id"),
                "response_model": response.get("model", self.model_id),
                "pre_gate_proposal_sha256": pre_gate_sha,
                "dynamic_gate": bool(self.contract.execution_gate),
            },
            receipts=receipts,
            cost=Cost(
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_calls=1,
                searches=0,
                tool_calls=1 if self.contract.structured_output else 0,
            ),
        )


__all__ = [
    "DynamicOpenAIResponsesAdapter",
    "OPENAI_RESPONSES_URL",
    "ReceiptBundleStore",
    "ResponsesTransport",
    "UrllibOpenAIResponsesTransport",
]
