from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .schema import Decision, Prediction, Task


DEFAULT_TOOLS = {
    "send_email",
    "copy_email",
    "archive_file",
    "delete_file",
    "approve_supplier",
    "create_contract",
    "transfer_object",
    "update_record",
    "rename_entity",
    "describe_entity",
    "record_relation",
    "address_person",
}


@dataclass(frozen=True)
class ToolCallRecord:
    task_id: str
    system_id: str
    tool: str
    arguments: Mapping[str, Any]
    admitted: bool
    reason: str


@dataclass
class ExecutionSandbox:
    registered_tools: set[str] = field(default_factory=lambda: set(DEFAULT_TOOLS))
    calls: list[ToolCallRecord] = field(default_factory=list)

    def execute(self, task: Task, prediction: Prediction) -> ToolCallRecord | None:
        if prediction.decision is not Decision.EXECUTE:
            return None

        tool = prediction.tool or ""
        admitted = True
        reason = "SIMULATED_EXECUTION"

        if tool not in self.registered_tools:
            admitted = False
            reason = "UNREGISTERED_TOOL"
        elif tool not in task.allowed_tools:
            admitted = False
            reason = "TOOL_NOT_ALLOWED_FOR_TASK"

        record = ToolCallRecord(
            task_id=task.task_id,
            system_id=prediction.system_id,
            tool=tool,
            arguments=dict(prediction.arguments),
            admitted=admitted,
            reason=reason,
        )
        self.calls.append(record)
        return record
