from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from scott_claude.core.events.bus import EventBus
from scott_claude.core.llm.types import LlmResponse, UsageStats
from scott_claude.core.trace.provider import TracingProvider
from scott_claude.core.trace.record import TraceRecord
from scott_claude.core.trace.writer import TraceWriter


def _make_response(stop_reason: str = "end_turn") -> LlmResponse:
    return LlmResponse(
        stop_reason=stop_reason,
        tool_calls=[],
        text="done",
        usage=UsageStats(
            input_tokens=10,
            output_tokens=5,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        ),
    )


async def _make_writer(tmp_path: Path) -> TraceWriter:
    w = TraceWriter(tmp_path / "trace.jsonl")
    await w.start()
    return w


# 功能：验证 chat() 调用前后各 emit 一条 CORE→LLM 和 LLM→CORE 记录
# 设计：mock inner provider，收集 TraceWriter 收到的 record；断言 direction 顺序和 kind
@pytest.mark.asyncio
async def test_emits_api_call_and_api_response(tmp_path: Path) -> None:
    records: list[TraceRecord] = []

    writer = await _make_writer(tmp_path)
    inner = AsyncMock()
    inner.chat = AsyncMock(return_value=_make_response())

    original_emit = writer.emit

    def capturing_emit(record: TraceRecord) -> None:
        records.append(record)
        original_emit(record)

    writer.emit = capturing_emit  # type: ignore[method-assign]

    provider = TracingProvider(inner, writer)
    bus = EventBus()

    await provider.chat(
        messages=[{"role": "user", "content": "hi"}],
        tool_schemas=[],
        bus=bus,
        run_id="run-1",
        step=2,
    )
    await writer.stop()

    assert len(records) == 2
    assert records[0].direction == "CORE→LLM"
    assert records[0].kind == "api_call"
    assert records[0].step == 2
    assert records[0].run_id == "run-1"
    assert records[1].direction == "LLM→CORE"
    assert records[1].kind == "api_response"
    assert records[1].step == 2


# 功能：验证 include_payload=True 时 data 包含完整 messages 和 response text
# 设计：断言 api_call.data["messages"] 存在且 api_response.data["text"] 存在
@pytest.mark.asyncio
async def test_include_payload_true_embeds_full_content(tmp_path: Path) -> None:
    records: list[TraceRecord] = []

    writer = await _make_writer(tmp_path)
    inner = AsyncMock()
    inner.chat = AsyncMock(return_value=_make_response())

    original_emit = writer.emit

    def capturing_emit(r: TraceRecord) -> None:
        records.append(r)
        original_emit(r)

    writer.emit = capturing_emit  # type: ignore[method-assign]

    provider = TracingProvider(inner, writer, include_payload=True)
    await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
        tool_schemas=[{"name": "foo"}],
        bus=EventBus(),
        run_id="r",
        step=1,
    )
    await writer.stop()

    assert "messages" in records[0].data
    assert "text" in records[1].data


# 功能：验证 include_payload=False 时只保留摘要字段，不包含完整 messages
# 设计：断言 api_call.data 只有 message_count/tool_count，不含 messages 键
@pytest.mark.asyncio
async def test_include_payload_false_uses_summary(tmp_path: Path) -> None:
    records: list[TraceRecord] = []

    writer = await _make_writer(tmp_path)
    inner = AsyncMock()
    inner.chat = AsyncMock(return_value=_make_response())

    original_emit = writer.emit

    def capturing_emit(r: TraceRecord) -> None:
        records.append(r)
        original_emit(r)

    writer.emit = capturing_emit  # type: ignore[method-assign]

    provider = TracingProvider(inner, writer, include_payload=False)
    await provider.chat(
        messages=[{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}],
        tool_schemas=[],
        bus=EventBus(),
        run_id="r",
        step=1,
    )
    await writer.stop()

    call_data = records[0].data
    assert "messages" not in call_data
    assert call_data["message_count"] == 2

    resp_data = records[1].data
    assert "text" not in resp_data
    assert "latency_ms" in resp_data


# 功能：验证 TracingProvider 将 step 参数透传给 inner provider
# 设计：用 AsyncMock 捕获 inner.chat 的调用参数，断言 step 关键字参数正确
@pytest.mark.asyncio
async def test_step_forwarded_to_inner_provider(tmp_path: Path) -> None:
    writer = await _make_writer(tmp_path)
    inner = AsyncMock()
    inner.chat = AsyncMock(return_value=_make_response())

    provider = TracingProvider(inner, writer)
    await provider.chat([], [], EventBus(), "r", step=7)
    await writer.stop()

    inner.chat.assert_called_once()
    _, kwargs = inner.chat.call_args
    assert kwargs["step"] == 7
