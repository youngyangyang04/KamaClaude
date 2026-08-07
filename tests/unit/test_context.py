from __future__ import annotations

from scott_claude.core.context import ExecutionContext


# 功能：验证 ExecutionContext 初始化时将 goal 包装为第一条 user 消息
# 设计：直接检查 messages 列表初始状态，不经过任何方法，因为这是 Anthropic messages 格式的起点，必须精确
def test_initial_message_is_goal() -> None:
    ctx = ExecutionContext(run_id="r1", goal="test goal", max_steps=5)
    assert ctx.messages == [{"role": "user", "content": "test goal"}]


# 功能：验证新建 context 的 is_done() 返回 False
# 设计：初始化后立即查询，无需任何操作，排除默认值错误导致 AgentLoop 在第一步就认为任务已完成
def test_is_done_returns_false_when_running() -> None:
    ctx = ExecutionContext(run_id="r1", goal="g", max_steps=5)
    assert not ctx.is_done()


# 功能：验证 mark_success 后 is_done、status、reason 三个字段同时反映成功状态
# 设计：同时断言三个字段，因为 AgentLoop 和 AgentRunner 都依赖这三者联合判断 run 结果
def test_mark_success() -> None:
    ctx = ExecutionContext(run_id="r1", goal="g", max_steps=5)
    ctx.mark_success()
    assert ctx.is_done()
    assert ctx.status == "success"
    assert ctx.reason is None


# 功能：验证 mark_failed 后 status 和 reason 被正确记录
# 设计：传入具体 reason 字符串，断言其在 context.reason 中完整保留，供 run.finished 事件使用
def test_mark_failed() -> None:
    ctx = ExecutionContext(run_id="r1", goal="g", max_steps=5)
    ctx.mark_failed("exceeded_max_steps")
    assert ctx.is_done()
    assert ctx.status == "failed"
    assert ctx.reason == "exceeded_max_steps"


# 功能：验证 add_assistant_message 追加符合 Anthropic 格式的消息（role=assistant）
# 设计：验证最后一条消息的 role 和 content 引用，确认 Anthropic API 所要求的消息结构
def test_add_assistant_message_appended() -> None:
    ctx = ExecutionContext(run_id="r1", goal="g", max_steps=5)
    content = [{"type": "text", "text": "I'll help"}]
    ctx.add_assistant_message(content)
    assert ctx.messages[-1] == {"role": "assistant", "content": content}


# 功能：验证工具结果被包装为 tool_result 类型的 user 消息，并带有正确的 tool_use_id
# 设计：先加含 tool_use block 的 assistant 消息（满足 Anthropic 要求），再调用 add_tool_result，检查最终消息结构
def test_add_tool_result_creates_user_message() -> None:
    ctx = ExecutionContext(run_id="r1", goal="g", max_steps=5)
    ctx.add_assistant_message(
        [{"type": "tool_use", "id": "toolu_01", "name": "read_file", "input": {"path": "x"}}]
    )
    ctx.add_tool_result("toolu_01", "file content")
    last = ctx.messages[-1]
    assert last["role"] == "user"
    assert last["content"][0]["type"] == "tool_result"
    assert last["content"][0]["tool_use_id"] == "toolu_01"
    assert last["content"][0]["content"] == "file content"


# 功能：验证同一步骤的多个工具结果被合并到一条 user 消息而非拆成多条
# 设计：连续两次 add_tool_result，断言消息总数为 3（goal + assistant + 合并 user）；Anthropic API 要求同一轮 tool_result 合并提交
def test_multiple_tool_results_share_one_message() -> None:
    ctx = ExecutionContext(run_id="r1", goal="g", max_steps=5)
    ctx.add_assistant_message([
        {"type": "tool_use", "id": "toolu_01", "name": "read_file", "input": {}},
        {"type": "tool_use", "id": "toolu_02", "name": "read_file", "input": {}},
    ])
    ctx.add_tool_result("toolu_01", "result A")
    ctx.add_tool_result("toolu_02", "result B")

    # goal + assistant + tool_results（合并为一条）
    assert len(ctx.messages) == 3
    last = ctx.messages[-1]
    assert last["role"] == "user"
    assert len(last["content"]) == 2
    assert last["content"][0]["tool_use_id"] == "toolu_01"
    assert last["content"][1]["tool_use_id"] == "toolu_02"


# 功能：验证失败的工具结果中 is_error 标记被正确传递到消息 block
# 设计：传入 is_error=True 后检查 block 中的字段，确认错误标记不丢失，LLM 在下一步能感知工具失败
def test_tool_result_error_flag() -> None:
    ctx = ExecutionContext(run_id="r1", goal="g", max_steps=5)
    ctx.add_assistant_message(
        [{"type": "tool_use", "id": "t1", "name": "x", "input": {}}]
    )
    ctx.add_tool_result("t1", "something failed", is_error=True)
    block = ctx.messages[-1]["content"][0]
    assert block["is_error"] is True
    assert block["content"] == "something failed"


# 功能：验证多轮步骤的消息 role 顺序符合 user-assistant 交替规则
# 设计：只检查 roles 列表，不检查 content，聚焦 Anthropic API 对交替消息格式的要求
def test_message_order_across_steps() -> None:
    ctx = ExecutionContext(run_id="r1", goal="g", max_steps=5)
    ctx.add_assistant_message([{"type": "text", "text": "step 1 plan"}])
    ctx.add_tool_result("t1", "tool result")
    ctx.add_assistant_message([{"type": "text", "text": "step 2 plan"}])

    roles = [m["role"] for m in ctx.messages]
    assert roles == ["user", "assistant", "user", "assistant"]


# 功能：验证步数计数器初始值为 0
# 设计：简单边界值测试，确认计数器起点，AgentLoop 依赖此初始值做步数限制判断
def test_step_counter_default() -> None:
    ctx = ExecutionContext(run_id="r1", goal="g", max_steps=20)
    assert ctx.step == 0
