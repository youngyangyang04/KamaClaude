from __future__ import annotations

from typing import Protocol

from scott_claude.core.events.bus import EventBus
from scott_claude.core.llm.types import LlmResponse


class LLMProvider(Protocol):
    # 流式调用 LLM 并发布进度事件，返回完整响应
    async def chat(
        self,
        messages: list[dict[str, object]],
        tool_schemas: list[dict[str, object]],
        bus: EventBus,
        run_id: str,
        *,
        step: int = 0,
        system: str | None = None,
    ) -> LlmResponse: ...
