from __future__ import annotations

import json

from scott_claude.core.task.manager import TaskManager
from scott_claude.core.task.model import TaskStatus
from scott_claude.core.tools.base import BaseTool, ToolResult


class TaskUpdateTool(BaseTool):
    name = "task_update"
    description = (
        "Update a task's status or dependency list. "
        "Set status to 'in_progress' when starting work on a task, "
        "'completed' when finished (automatically clears it from other tasks' blocked_by). "
        "Returns the updated task as JSON."
    )
    input_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "integer",
                "description": "ID of the task to update.",
            },
            "status": {
                "type": "string",
                "enum": ["pending", "in_progress", "completed"],
                "description": "New status for the task.",
            },
            "add_blocked_by": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Task IDs to add to blocked_by.",
            },
            "remove_blocked_by": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Task IDs to remove from blocked_by.",
            },
        },
        "required": ["task_id"],
    }

    # 持有 TaskManager 实例，供 invoke 调用
    def __init__(self, task_manager: TaskManager) -> None:
        self._manager = task_manager

    # 更新任务并返回 JSON 字符串
    async def invoke(self, params: dict[str, object]) -> ToolResult:
        task_id = int(str(params["task_id"]))
        status: TaskStatus | None = params.get("status")  # type: ignore[assignment]
        raw_add: list[object] = list(params.get("add_blocked_by") or [])  # type: ignore[call-overload]
        raw_rem: list[object] = list(params.get("remove_blocked_by") or [])  # type: ignore[call-overload]
        add_blocked = [int(str(x)) for x in raw_add]
        remove_blocked = [int(str(x)) for x in raw_rem]
        try:
            task = self._manager.update(
                task_id,
                status=status,
                add_blocked_by=add_blocked or None,
                remove_blocked_by=remove_blocked or None,
            )
            return ToolResult(content=json.dumps(task.to_dict(), ensure_ascii=False))
        except ValueError as exc:
            return ToolResult(content=str(exc), is_error=True, error_type="runtime_error")
