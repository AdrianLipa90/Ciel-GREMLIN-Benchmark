from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Mapping, Protocol
from urllib import error, request

from .schema import Cost, Decision, Prediction, Task
from .systems import get_system_contract


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
_DECISION_TOOL = "submit_benchmark_decision"
_ALLOWED_MODEL_PARAMETERS = frozenset({
    "temperature",
    "top_p",
    "max_output_tokens",
    "reasoning",
    "service_tier",
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


class ResponsesTransport(Protocol):
    def create_response(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        ...


class UrllibOpenAIResponsesTransport:
    """Minimal Responses API transport with no third-party runtime dependency."""

    def __init__(
        self,
        *,
        api_key_env: str = "OPENAI_API_KEY",
        url: str = OPENAI_RESPONSES_URL,
        timeout_s: float = 120.0,
    ) -> None:
        key = os.environ.get(api_key_env, "").strip()
        if not key:
            raise RuntimeError(f"missing API key environment variable {api_key_env!r}")
        if not url.startswith("https://"):
            raise ValueError("Responses API URL must use HTTPS")
        self._api_key = key
        self._url = url
        self._timeout_s = float(timeout_s)

    def create_response(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        body = _canonical_json(dict(payload)).encode("utf-8")
        req = request.Request(
            self._url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with request.urlopen(req, timeout=self._timeout_s) as response:
                raw = response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:2000]
            raise RuntimeError(f"OpenAI Responses API HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"OpenAI Responses API network error: {exc.reason}") from exc
        decoded = json.loads(raw.decode("utf-8"))
        if not isinstance(decoded, Mapping):
            raise RuntimeError("OpenAI Responses API returned non-object JSON")
        return decoded


@dataclass(frozen=True)
class ReceiptBundle:
    task_id: str
    gremlin: Mapping[str, Any] | None = None
    ciel: Mapping[str, Any] | None = None
    execution_gate: Mapping[str, Any] | None = None


class ReceiptBundleStore:
    def __init__(self, bundles: Mapping[str, ReceiptBundle]) -> None:
        self._bundles = dict(bundles)

    @classmethod
    def from_jsonl(cls, path: str | Path) -> "ReceiptBundleStore":
        bundles: dict[str, ReceiptBundle] = {}
        with Path(path).open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                raw = json.loads(line)
                if not isinstance(raw, Mapping):
                    raise ValueError(f"{path}:{line_no}: receipt row must be an object")
                task_id = str(raw.get("task_id", ""))
                if not task_id:
                    raise ValueError(f"{path}:{line_no}: task_id is required")
                if task_id in bundles:
                    raise ValueError(f"{path}:{line_no}: duplicate task_id={task_id!r}")
                bundles[task_id] = ReceiptBundle(
                    task_id=task_id,
                    gremlin=dict(raw["gremlin"]) if isinstance(raw.get("gremlin"), Mapping) else None,
                    ciel=dict(raw["ciel"]) if isinstance(raw.get("ciel"), Mapping) else None,
                    execution_gate=(
                        dict(raw["execution_gate"])
                        if isinstance(raw.get("execution_gate"), Mapping)
                        else None
                    ),
                )
        return cls(bundles)

    def get(self, task_id: str) -> ReceiptBundle | None:
        return self._bundles.get(task_id)


def _task_payload(task: Task, *, gremlin: Mapping[str, Any] | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "task_id": task.task_id,
        "language": task.language,
        "user_input": task.user_input,
        "world_state": dict(task.world_state),
        "evidence": [dict(item) for item in task.evidence],
        "allowed_tools": list(task.allowed_tools),
        "tags": list(task.tags),
    }
    if gremlin is not None:
        payload["gremlin_research_receipt"] = dict(gremlin)
    return payload


def _decision_tool(task: Task) -> dict[str, Any]:
    return {
        "type": "function",
        "name": _DECISION_TOOL,
        "description": "Submit exactly one benchmark execution decision.",
        "parameters": {
            "type": "object",
            "properties": {
                "decision": {
                    "type": "string",
                    "enum": [decision.value for decision in Decision],
                },
                "tool": {
                    "type": "string",
                    "enum": ["", *task.allowed_tools],
                },
                "arguments_json": {
                    "type": "string",
                    "description": "JSON object string with tool arguments; use {} when not executing.",
                },
            },
            "required": ["decision", "tool", "arguments_json"],
            "additionalProperties": False,
        },
        "strict": True,
    }


def _response_output_text(response: Mapping[str, Any]) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    pieces: list[str] = []
    for item in response.get("output") or []:
        if not isinstance(item, Mapping) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if isinstance(content, Mapping) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str):
                    pieces.append(text)
    return "\n".join(pieces).strip()


def _parse_unstructured_decision(response: Mapping[str, Any]) -> tuple[Decision, str | None, dict[str, Any]]:
    text = _response_output_text(response)
    if not text:
        raise ValueError("B0 response contains no output text")
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("B0 response is not a single JSON object") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("B0 response JSON must be an object")
    decision = Decision(str(raw.get("decision", "")))
    tool_raw = raw.get("tool")
    tool = str(tool_raw).strip() if tool_raw not in (None, "") else None
    args = raw.get("arguments") or {}
    if not isinstance(args, Mapping):
        raise ValueError("B0 arguments must be an object")
    return decision, tool, dict(args)


def _parse_structured_decision(response: Mapping[str, Any]) -> tuple[Decision, str | None, dict[str, Any]]:
    calls = [
        item
        for item in (response.get("output") or [])
        if isinstance(item, Mapping)
        and item.get("type") == "function_call"
        and item.get("name") == _DECISION_TOOL
    ]
    if len(calls) != 1:
        raise ValueError(f"expected exactly one {_DECISION_TOOL} function call")
    args_raw = calls[0].get("arguments")
    if not isinstance(args_raw, str):
        raise ValueError("function-call arguments must be a JSON string")
    args = json.loads(args_raw)
    if not isinstance(args, Mapping):
        raise ValueError("function-call arguments must decode to an object")
    decision = Decision(str(args.get("decision", "")))
    tool_raw = args.get("tool")
    tool = str(tool_raw).strip() if tool_raw not in (None, "") else None
    arguments_json = args.get("arguments_json", "{}")
    if not isinstance(arguments_json, str):
        raise ValueError("arguments_json must be a string")
    tool_args = json.loads(arguments_json)
    if not isinstance(tool_args, Mapping):
        raise ValueError("arguments_json must decode to an object")
    return decision, tool, dict(tool_args)


def _apply_execution_gate(
    decision: Decision,
    tool: str | None,
    arguments: dict[str, Any],
    gate: Mapping[str, Any],
) -> tuple[Decision, str | None, dict[str, Any]]:
    action = str(gate.get("action", "")).upper()
    if action == "ALLOW":
        return decision, tool, arguments
    mapping = {
        "ASK": Decision.ASK,
        "REJECT": Decision.REJECT,
        "DEFER": Decision.DEFER,
    }
    if action not in mapping:
        raise ValueError("execution_gate.action must be ALLOW, ASK, REJECT, or DEFER")
    return mapping[action], None, {}


class OpenAIResponsesAdapter:
    """Live B0-B4 adapter using the OpenAI Responses API.

    GREMLIN evidence is injected before the model for B2/B4. CIEL and execution-gate
    receipts are applied after model interpretation for B3/B4, preserving the ablation
    distinction between research context and semantic execution control.
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
    ) -> None:
        self.system_id = system_id
        self.contract = get_system_contract(system_id)
        self.model_id = str(model_id)
        self.prompt = str(prompt)
        self.transport = transport
        self.receipt_store = receipt_store
        self.model_parameters = dict(model_parameters or {})
        unknown = set(self.model_parameters) - _ALLOWED_MODEL_PARAMETERS
        if unknown:
            raise ValueError(f"unsupported Responses API model parameters: {sorted(unknown)}")

    def _receipts_for_task(self, task: Task) -> ReceiptBundle:
        bundle = self.receipt_store.get(task.task_id) if self.receipt_store else None
        if bundle is None:
            bundle = ReceiptBundle(task_id=task.task_id)
        if self.contract.gremlin and bundle.gremlin is None:
            raise ValueError(f"{task.task_id}: {self.system_id} requires GREMLIN receipt")
        if self.contract.ciel and bundle.ciel is None:
            raise ValueError(f"{task.task_id}: {self.system_id} requires CIEL receipt")
        if self.contract.execution_gate and bundle.execution_gate is None:
            raise ValueError(f"{task.task_id}: {self.system_id} requires execution-gate receipt")
        return bundle

    def _request_payload(self, task: Task, bundle: ReceiptBundle) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model_id,
            "instructions": self.prompt,
            "input": _canonical_json(_task_payload(task, gremlin=bundle.gremlin if self.contract.gremlin else None)),
            "store": False,
        }
        payload.update(self.model_parameters)
        if self.contract.structured_output:
            payload.update({
                "tools": [_decision_tool(task)],
                "tool_choice": {"type": "function", "name": _DECISION_TOOL},
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

        if self.contract.execution_gate:
            assert bundle.execution_gate is not None
            decision, tool, arguments = _apply_execution_gate(
                decision,
                tool,
                arguments,
                bundle.execution_gate,
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
                "strict_function": _DECISION_TOOL,
            }
        if self.contract.gremlin:
            receipts["gremlin"] = dict(bundle.gremlin or {})
        if self.contract.ciel:
            receipts["ciel"] = dict(bundle.ciel or {})
        if self.contract.execution_gate:
            receipts["execution_gate"] = dict(bundle.execution_gate or {})

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
    "OPENAI_RESPONSES_URL",
    "OpenAIResponsesAdapter",
    "ReceiptBundle",
    "ReceiptBundleStore",
    "ResponsesTransport",
    "UrllibOpenAIResponsesTransport",
]
