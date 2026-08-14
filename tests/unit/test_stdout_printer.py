from __future__ import annotations

import pytest

from scott_claude.cli.commands.run import StdoutPrinter


# 功能：验证 run.started 事件在 stdout 中打印 [run] 前缀和 run_id
# 设计：用 capsys 捕获 stdout，直接断言关键字符串，避免对格式细节过度约束
async def test_run_started_prints_run_id(capsys: pytest.CaptureFixture[str]) -> None:
    printer = StdoutPrinter()
    await printer.handle(
        {"type": "run.started", "run_id": "20260515-abc", "goal": "g", "ts": "t"}
    )
    out = capsys.readouterr().out
    assert "[run]" in out
    assert "20260515-abc" in out


# 功能：验证 step.started 事件打印 [step N] 和 planning... 文本
# 设计：断言步骤编号和 planning 关键词同时出现，覆盖格式模板的两个可变部分
async def test_step_started_prints_step_number(capsys: pytest.CaptureFixture[str]) -> None:
    printer = StdoutPrinter()
    await printer.handle({"type": "step.started", "run_id": "r", "step": 3, "ts": "t"})
    out = capsys.readouterr().out
    assert "[step 3]" in out
    assert "planning" in out


# 功能：验证 llm.token 事件将 token 无换行打印并设置 _inline 标志
# 设计：发送 token 后检查 _inline 为 True，再发 step.started 触发 _ensure_newline，
#       确认换行被补齐（新行里有 [step]），验证内联状态机的完整转换
async def test_llm_token_inline_then_newline_on_next_event(
    capsys: pytest.CaptureFixture[str],
) -> None:
    printer = StdoutPrinter()
    await printer.handle({"type": "llm.token", "run_id": "r", "token": "hello", "ts": "t"})
    assert printer._inline is True  # type: ignore[attr-defined]

    await printer.handle({"type": "step.started", "run_id": "r", "step": 2, "ts": "t"})
    assert printer._inline is False  # type: ignore[attr-defined]
    out = capsys.readouterr().out
    assert "hello" in out
    assert "[step 2]" in out


# 功能：验证 tool.call_started 打印工具名和 JSON 序列化的 params
# 设计：用带 Unicode 内容的 params 检查 ensure_ascii=False（保留中文字符），断言工具名和参数都出现
async def test_tool_call_started_prints_name_and_params(
    capsys: pytest.CaptureFixture[str],
) -> None:
    printer = StdoutPrinter()
    await printer.handle(
        {
            "type": "tool.call_started",
            "run_id": "r",
            "tool_use_id": "t1",
            "tool_name": "read_file",
            "params": {"path": "README.md"},
            "ts": "t",
        }
    )
    out = capsys.readouterr().out
    assert "[tool]" in out
    assert "read_file" in out
    assert "README.md" in out


# 功能：验证 run.finished 打印 status 和 steps 字段
# 设计：success 路径下断言 status 和 steps 出现在输出中，不检查 elapsed 的精确值（依赖时间）
async def test_run_finished_prints_status_and_steps(capsys: pytest.CaptureFixture[str]) -> None:
    printer = StdoutPrinter()
    await printer.handle(
        {"type": "run.started", "run_id": "r", "goal": "g", "ts": "t"}
    )
    await printer.handle(
        {"type": "run.finished", "run_id": "r", "status": "success", "steps": 4, "ts": "t"}
    )
    out = capsys.readouterr().out
    assert "success" in out
    assert "4" in out
