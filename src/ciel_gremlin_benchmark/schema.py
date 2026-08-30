from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class Decision(str, Enum):
    EXECUTE = "EXECUTE"
    ASK = "ASK"
    REJECT = "REJECT"
    DEFER = "DEFER"


class Family(str, Enum):
    F1_ENTITY_RECIPIENT = "F1_ENTITY_RECIPIENT"
    F2_OBJECT_ACTION = "F2_OBJECT_ACTION"
    F3_SCOPE_CONDITION = "F3_SCOPE_CONDITION"
    F4_EVIDENCE = "F4_EVIDENCE"
    F5_CROSS_LANGUAGE = "F5_CROSS_LANGUAGE"
    F6_NARY_RELATION = "F6_NARY_RELATION"


@dataclass(frozen=True)
class GroundTruth:
    decision: Decision
    tool: str | None = None
    arguments: Mapping[str, Any] = field(default_factory=dict)
    reason_code: str | None = None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "GroundTruth":
        return cls(
            decision=Decision(raw["decision"]),
            tool=raw.get("tool"),
            arguments=dict(raw.get("arguments") or {}),
            reason_code=raw.get("reason_code"),
        )

    def validate(self, allowed_tools: tuple[str, ...]) -> list[str]:
        issues: list[str] = []
        if self.decision is Decision.EXECUTE:
            if not self.tool:
                issues.append("EXECUTE ground truth requires tool")
            elif self.tool not in allowed_tools:
                issues.append(f"ground-truth tool {self.tool!r} is not allowed")
        else:
            if self.tool is not None:
                issues.append("non-EXECUTE ground truth must not define tool")
            if self.arguments:
                issues.append("non-EXECUTE ground truth must not define arguments")
        return issues


@dataclass(frozen=True)
class Task:
    task_id: str
    family: Family
    language: str
    user_input: str
    world_state: Mapping[str, Any]
    evidence: tuple[Mapping[str, Any], ...]
    allowed_tools: tuple[str, ...]
    ground_truth: GroundTruth
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Task":
        return cls(
            task_id=str(raw["task_id"]),
            family=Family(raw["family"]),
            language=str(raw["language"]),
            user_input=str(raw["user_input"]),
            world_state=dict(raw.get("world_state") or {}),
            evidence=tuple(dict(item) for item in (raw.get("evidence") or [])),
            allowed_tools=tuple(str(x) for x in (raw.get("allowed_tools") or [])),
            ground_truth=GroundTruth.from_dict(raw["ground_truth"]),
            tags=tuple(str(x) for x in (raw.get("tags") or [])),
            metadata=dict(raw.get("metadata") or {}),
        )

    def validate(self) -> list[str]:
        issues: list[str] = []
        if not self.task_id:
            issues.append("task_id is empty")
        if not self.user_input.strip():
            issues.append("user_input is empty")
        if not self.language:
            issues.append("language is empty")
        if len(set(self.allowed_tools)) != len(self.allowed_tools):
            issues.append("allowed_tools contains duplicates")
        issues.extend(self.ground_truth.validate(self.allowed_tools))
        return issues


@dataclass(frozen=True)
class Cost:
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    model_calls: int = 0
    searches: int = 0
    tool_calls: int = 0

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "Cost":
        raw = raw or {}
        return cls(
            latency_ms=float(raw.get("latency_ms", 0.0)),
            input_tokens=int(raw.get("input_tokens", 0)),
            output_tokens=int(raw.get("output_tokens", 0)),
            model_calls=int(raw.get("model_calls", 0)),
            searches=int(raw.get("searches", 0)),
            tool_calls=int(raw.get("tool_calls", 0)),
        )


@dataclass(frozen=True)
class Prediction:
    system_id: str
    task_id: str
    decision: Decision
    tool: str | None = None
    arguments: Mapping[str, Any] = field(default_factory=dict)
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    receipts: Mapping[str, Any] = field(default_factory=dict)
    cost: Cost = field(default_factory=Cost)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Prediction":
        return cls(
            system_id=str(raw["system_id"]),
            task_id=str(raw["task_id"]),
            decision=Decision(raw["decision"]),
            tool=raw.get("tool"),
            arguments=dict(raw.get("arguments") or {}),
            diagnostics=dict(raw.get("diagnostics") or {}),
            receipts=dict(raw.get("receipts") or {}),
            cost=Cost.from_dict(raw.get("cost")),
        )

    def validate(self) -> list[str]:
        issues: list[str] = []
        if not self.system_id:
            issues.append("system_id is empty")
        if not self.task_id:
            issues.append("task_id is empty")
        if self.decision is Decision.EXECUTE:
            if not self.tool:
                issues.append("EXECUTE prediction requires tool")
        else:
            if self.tool is not None:
                issues.append("non-EXECUTE prediction must not define tool")
            if self.arguments:
                issues.append("non-EXECUTE prediction must not define arguments")
        return issues
