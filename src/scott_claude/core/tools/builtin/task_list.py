from __future__ import annotations

from scott_claude.core.task.manager import TaskManager
from scott_claude.core.tools.base import BaseTool, ToolResult


class TaskListTool(BaseTool):
    name = "task_list"
    description = (
        "List all tasks with their current status and blocking dependencies. "
        "Use this to check what work remains and what can be started next."
    )
    input_schema: dict[str, object] = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    # 持有 TaskManager 实例，供 invoke 调用
    def __init__(self, task_manager: TaskManager) -> None:
        self._manager = task_manager

    # 返回格式化的任务列表摘要
    async def invoke(self, params: dict[str, object]) -> ToolResult:
        return ToolResult(content=self._manager.format_list())
