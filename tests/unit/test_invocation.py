from __future__ import annotations

import asyncio

from pydantic import BaseModel

from scott_claude.core.events.bus import EventBus
from scott_claude.core.llm.types import ToolCallBlock
from scott_claude.core.tools.base import BaseTool, ToolResult
from scott_claude.core.tools.invocation import invoke_tool
from scott_claude.core.tools.registry import ToolRegistry

# --- stub tools --------------------------------------------------------------


class _EchoParams(BaseModel):
    msg: str


class _EchoTool(BaseTool):
    name = "echo"
    description = "Echoes the msg param"
    input_schema: dict[str, object] = {
        "type": "object",
        "properties": {"msg": {"type": "string"}},
        "required": ["msg"],
    }
    params_model = _EchoParams

    async def invoke(self, params: dict[str, object]) -> ToolResult:
        return ToolResult(content=str(params["msg"]))


class _SlowTool(BaseTool):
    name = "slow"
    description = "Sleeps forever"
    input_schema: dict[str, object] = {"type": "object", "properties": {}, "required": []}

    async def invoke(self, params: dict[str, object]) -> ToolResult:
        await asyncio.sleep(60)
        return ToolResult(content="done")


class _BrokenTool(BaseTool):
    name = "broken"
    description = "Always raises"
    input_schema: dict[str, object] = {"type": "object", "properties": {}, "required": []}

    async def invoke(self, params: dict[str, object]) -> ToolResult:
        raise RuntimeError("boom")


# --- helpers -----------------------------------------------------------------


def _call(name: str, inp: dict[str, object] | None = None, uid: str = "t1") -> ToolCallBlock:
    return ToolCallBlock(id=uid, name=name, input=inp or {})


async def _run(
    registry: ToolRegistry,
    tool_call: ToolCallBlock,
    timeout: float = 5.0,
) -> tuple[ToolResult, list[BaseModel]]:
    bus = EventBus()
    events: list[BaseModel] = []

    async def _collect(e: BaseModel) -> None:
        events.append(e)

    bus.subscribe(_collect)
    result = await invoke_tool(registry, tool_call, bus, run_id="r1", timeout=timeout)
    return result, events


# --- tests -------------------------------------------------------------------


# 功能：验证正常调用时返回工具内容且发布 started + finished 事件
# 设计：同时检查返回值和事件序列，因为 invoke_tool 的双重职责是"返回结果 + 发布事件"，缺一不可
async def test_success_returns_content_and_finished_event() -> None:
    registry = ToolRegistry()
    registry.register(_EchoTool())
    result, events = await _run(registry, _call("echo", {"msg": "hi"}))
    assert not result.is_error
    assert result.content == "hi"
    types = [e.type for e in events]  # type: ignore[attr-defined]
    assert types[0] == "tool.call_started"
    assert "tool.call_finished" in types
    assert "tool.call_failed" not in types


# 功能：验证调用不存在的工具时返回 runtime_error 并发布 failed 事件而非 finished
# 设计：传入空 registry，确认 error_type 和事件类型同时正确，排除"未知工具却发布了 finished"的情况
async def test_unknown_tool_returns_runtime_error() -> None:
    result, events = await _run(ToolRegistry(), _call("nonexistent"))
    assert result.is_error
    assert result.error_type == "runtime_error"
    assert "unknown tool" in result.content
    types = [e.type for e in events]  # type: ignore[attr-defined]
    assert "tool.call_started" in types
    assert "tool.call_failed" in types
    assert "tool.call_finished" not in types


# 功能：验证缺少必填参数时返回 schema_error 而非 runtime_error
# 设计：注册需要 msg 参数的 EchoTool 但传空 input，确认错误分类准确，schema 错误与运行时错误对 S4 重试策略有不同影响
async def test_missing_required_param_gives_schema_error() -> None:
    registry = ToolRegistry()
    registry.register(_EchoTool())
    result, events = await _run(registry, _call("echo", {}))  # "msg" is required
    assert result.is_error
    assert result.error_type == "schema_error"
    types = [e.type for e in events]  # type: ignore[attr-defined]
    assert "tool.call_failed" in types


# 功能：验证工具执行超时时返回 timeout 类型错误而非 runtime_error
# 设计：使用永久 sleep 的 SlowTool + 极短超时（50ms），测试 asyncio.wait_for 的超时路径，确认超时被正确分类
async def test_timeout_gives_timeout_error() -> None:
    registry = ToolRegistry()
    registry.register(_SlowTool())
    result, events = await _run(registry, _call("slow"), timeout=0.05)
    assert result.is_error
    assert result.error_type == "timeout"
    types = [e.type for e in events]  # type: ignore[attr-defined]
    assert "tool.call_failed" in types


# 功能：验证工具内部抛出异常时被捕获并转为 runtime_error，错误信息保留原始异常消息
# 设计：工具直接 raise RuntimeError，确认异常不向上传播（invoke_tool 的"不抛异常"契约），error_message 包含 "boom"
async def test_runtime_exception_gives_runtime_error() -> None:
    registry = ToolRegistry()
    registry.register(_BrokenTool())
    result, events = await _run(registry, _call("broken"))
    assert result.is_error
    assert result.error_type == "runtime_error"
    assert "boom" in result.content


# 功能：验证 tool.call_started 始终是第一个被发布的事件，即使工具调用最终失败
# 设计：用不存在的工具触发失败路径，确认即使失败也先发布 started，保证事件流的时序可观测性
async def test_started_event_always_first() -> None:
    result, events = await _run(ToolRegistry(), _call("nonexistent"))
    assert events[0].type == "tool.call_started"  # type: ignore[attr-defined]
