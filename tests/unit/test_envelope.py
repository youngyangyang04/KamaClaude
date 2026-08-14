from __future__ import annotations

import pytest
from pydantic import ValidationError

from scott_claude.core.bus.envelope import (
    PARSE_ERROR,
    JsonRpcRequest,
    JsonRpcSuccess,
    make_error,
)


# 功能：验证 JsonRpcRequest 序列化后再反序列化，所有字段值完整保留
# 设计：JSON 往返（model_dump_json → model_validate_json）确认字段完整性，这是 NDJSON wire 协议的基本契约
def test_request_roundtrip() -> None:
    req = JsonRpcRequest(id="1", method="core.ping", params={"client": "test"})
    req2 = JsonRpcRequest.model_validate_json(req.model_dump_json())
    assert req2.id == "1"
    assert req2.method == "core.ping"
    assert req2.params == {"client": "test"}


# 功能：验证 params 字段的默认值为空字典而非 None
# 设计：不传 params 参数实例化，确认默认值为 {}，避免 SocketServer handler 对 params 做 None 判断
def test_request_default_params() -> None:
    req = JsonRpcRequest(id="1", method="x")
    assert req.params == {}


# 功能：验证缺少必填 id 字段时 pydantic 校验失败
# 设计：传入无 id 的 dict，确认 id 是必填字段，防止无 id 请求绕过 JSON-RPC 格式校验进入 handler
def test_request_missing_id_raises() -> None:
    with pytest.raises(ValidationError):
        JsonRpcRequest.model_validate({"jsonrpc": "2.0", "method": "x"})


# 功能：验证 jsonrpc 字段非 "2.0" 时 pydantic 校验失败
# 设计：传入 "1.0" 确认 Literal["2.0"] 约束生效，jsonrpc 版本字段是协议兼容性的守门员
def test_request_wrong_version_raises() -> None:
    with pytest.raises(ValidationError):
        JsonRpcRequest.model_validate({"jsonrpc": "1.0", "id": "1", "method": "x"})


# 功能：验证 JsonRpcSuccess 序列化往返后 result 字段（Any 类型）保持原始嵌套结构
# 设计：result 是 Any 类型，往返测试确认嵌套 dict 不被丢弃或扁平化
def test_success_roundtrip() -> None:
    resp = JsonRpcSuccess(id="1", result={"key": "value"})
    resp2 = JsonRpcSuccess.model_validate_json(resp.model_dump_json())
    assert resp2.id == "1"
    assert resp2.result == {"key": "value"}


# 功能：验证 make_error 工厂函数正确设置 code、id 字段，data 默认为 None
# 设计：传入具名错误码常量（PARSE_ERROR），确认工厂函数不改变错误码值，同时验证 data=None 的默认行为
def test_make_error_sets_code() -> None:
    err = make_error("1", PARSE_ERROR, "Parse error")
    assert err.error.code == PARSE_ERROR
    assert err.id == "1"
    assert err.error.data is None


# 功能：验证 make_error 接受 None id（对应无法解析请求 id 时的错误响应）
# 设计：JSON-RPC 规范在无法解析 id 时允许 id=null，确认 pydantic 模型的 id: str | None 约束正确建模
def test_make_error_null_id() -> None:
    err = make_error(None, PARSE_ERROR, "bad json")
    assert err.id is None
