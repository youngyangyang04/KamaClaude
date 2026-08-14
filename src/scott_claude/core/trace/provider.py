from __future__ import annotations

import dataclasses
import time
from datetime import UTC, datetime
from typing import Any

from scott_claude.core.events.bus import EventBus
from scott_claude.core.llm.base import LLMProvider
from scott_claude.core.llm.types import LlmResponse
from scott_claude.core.trace.record import TraceRecord
from scott_claude.core.trace.writer import TraceWriter


def _now() -> str:
    return datetime.now(UTC).isoformat()


class TracingProvider:
    # 包裹真实 LLMProvider，在每次 chat() 调用前后向 TraceWriter 写入完整 API I/O 记录
    def __init__(
        self,
        inner: LLMProvider,
        trace: TraceWriter,
        *,
        include_payload: bool = True,
    ) -> None:
        self._inner = inner
        self._trace = trace
        self._include_payload = include_payload

    # 记录 CORE→LLM 请求，调用真实 provider，记录 LLM→CORE 响应（含延迟）
    async def chat(
        self,
        messages: list[dict[str, object]],
        tool_schemas: list[dict[str, object]],
        bus: EventBus,
        run_id: str,
        *,
        step: int = 0,
        system: str | None = None,
    ) -> LlmResponse:
        call_data: dict[str, Any]
        if self._include_payload:
            call_data = {"messages": messages, "tool_schemas": tool_schemas, "system": system}
        else:
            call_data = {
                "message_count": len(messages),
                "tool_count": len(tool_schemas),
            }

        self._trace.emit(
            TraceRecord(
                ts=_now(),
                direction="CORE→LLM",
                layer="llm",
                kind="api_call",
                run_id=run_id,
                step=step,
                data=call_data,
            )
        )

        t0 = time.monotonic()
        result = await self._inner.chat(
            messages, tool_schemas, bus, run_id, step=step, system=system
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        resp_data: dict[str, Any]
        if self._include_payload:
            resp_data = {
                "stop_reason": result.stop_reason,
                "text": result.text,
                "tool_calls": [dataclasses.asdict(tc) for tc in result.tool_calls],
                "usage": dataclasses.asdict(result.usage) if result.usage else {},
                "latency_ms": latency_ms,
            }
        else:
            resp_data = {
                "stop_reason": result.stop_reason,
                "usage": dataclasses.asdict(result.usage) if result.usage else {},
                "latency_ms": latency_ms,
            }

        self._trace.emit(
            TraceRecord(
                ts=_now(),
                direction="LLM→CORE",
                layer="llm",
                kind="api_response",
                run_id=run_id,
                step=step,
                data=resp_data,
            )
        )

        return result
