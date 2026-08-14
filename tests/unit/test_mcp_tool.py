from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from scott_claude.core.mcp.client import McpClient, McpServerUnavailableError, McpToolDef
from scott_claude.core.mcp.tool import McpTool


def _make_tool(
    tool_name: str = "read_file",
    server_name: str = "filesystem",
) -> tuple[McpTool, AsyncMock]:
    client = AsyncMock(spec=McpClient)
    tool_def = McpToolDef(
        name=tool_name,
        description=f"Read a file via {server_name}",
        input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
    )
    tool = McpTool(client, server_name, tool_def)
    return tool, client


# 功能：McpTool.invoke 应调用 client.call_tool 并将返回值封装为 ToolResult
# 设计：mock client.call_tool 返回固定字符串，验证 ToolResult.content 一致
@pytest.mark.asyncio
async def test_invoke_calls_mcp_client() -> None:
    tool, client = _make_tool()
    client.call_tool = AsyncMock(return_value="file content here")
    result = await tool.invoke({"path": "/tmp/test.txt"})
    assert not result.is_error
    assert result.content == "file content here"
    client.call_tool.assert_called_once_with("read_file", {"path": "/tmp/test.txt"})


# 功能：工具名应以 {server_name}__ 为前缀防止命名冲突
# 设计：验证 McpTool.name 格式为 "filesystem__read_file"
def test_tool_name_prefixed() -> None:
    tool, _ = _make_tool("read_file", "filesystem")
    assert tool.name == "filesystem__read_file"


# 功能：client 抛 McpServerUnavailableError 时应返回 is_error=True 且不重新抛出
# 设计：mock client.call_tool 抛该异常，断言 ToolResult.is_error=True 且消息含 server 名称
@pytest.mark.asyncio
async def test_unavailable_returns_error() -> None:
    tool, client = _make_tool()
    client.call_tool = AsyncMock(side_effect=McpServerUnavailableError("process died"))
    result = await tool.invoke({"path": "/tmp/x.txt"})
    assert result.is_error
    assert result.error_type == "runtime_error"
    assert "filesystem" in result.content


# 功能：client 抛其他异常时应返回 runtime_error 类型的 ToolResult
# 设计：mock client.call_tool 抛 RuntimeError，断言 ToolResult 被正确包装
@pytest.mark.asyncio
async def test_runtime_error_caught() -> None:
    tool, client = _make_tool()
    client.call_tool = AsyncMock(side_effect=RuntimeError("unexpected failure"))
    result = await tool.invoke({"path": "/tmp/y.txt"})
    assert result.is_error
    assert result.error_type == "runtime_error"
    assert "unexpected failure" in result.content


# 功能：input_schema 应直接使用 MCP tool_def 中的 schema，而非 pydantic model
# 设计：验证 params_model 为 None，input_schema 与 tool_def.input_schema 一致
def test_input_schema_from_tool_def() -> None:
    tool, _ = _make_tool()
    assert McpTool.params_model is None
    assert "path" in tool.input_schema.get("properties", {})
