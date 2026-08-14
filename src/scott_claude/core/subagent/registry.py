from __future__ import annotations

import asyncio

from scott_claude.core.context import ExecutionContext


# 管理后台 subagent 任务的生命周期：注册、查询、批量取消
class BackgroundTaskRegistry:
    def __init__(self) -> None:
        self._tasks: dict[str, tuple[asyncio.Task[None], ExecutionContext]] = {}

    # 注册一个后台任务及其执行上下文
    def register(
        self,
        run_id: str,
        task: asyncio.Task[None],
        context: ExecutionContext,
    ) -> None:
        self._tasks[run_id] = (task, context)

    # 查询后台任务及其上下文；不存在时返回 None
    def get(self, run_id: str) -> tuple[asyncio.Task[None], ExecutionContext] | None:
        return self._tasks.get(run_id)

    # 返回所有已注册的 (task, context) 对，用于 daemon 退出时批量清理
    def all(self) -> list[tuple[asyncio.Task[None], ExecutionContext]]:
        return list(self._tasks.values())
