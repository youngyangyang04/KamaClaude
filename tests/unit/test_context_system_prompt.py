from __future__ import annotations

from scott_claude.core.context import ExecutionContext


def _make_ctx(**kwargs) -> ExecutionContext:
    defaults = dict(run_id="r1", goal="test goal", max_steps=5)
    defaults.update(kwargs)
    return ExecutionContext(**defaults)


# 功能：验证三层记忆全部存在时都出现在 system prompt 中且顺序正确
# 设计：分别设置 global_context、project_context、session_notes，断言各 section 标题及内容依次出现
def test_all_layers_present() -> None:
    ctx = _make_ctx(
        global_context="global line",
        project_context="project line",
        session_notes="session note",
    )
    prompt = ctx.system_prompt("BASE")
    assert "BASE" in prompt
    assert "## Global Context\nglobal line" in prompt
    assert "## Project Context\nproject line" in prompt
    assert "## Session Notes\nsession note" in prompt
    # 顺序：global 在 project 之前，project 在 session 之前
    assert prompt.index("Global") < prompt.index("Project") < prompt.index("Session")


# 功能：验证三层均为空时 system prompt 只含 base
# 设计：不设置任何记忆字段，断言输出等于 base
def test_no_layers() -> None:
    ctx = _make_ctx()
    prompt = ctx.system_prompt("BASE_ONLY")
    assert prompt == "BASE_ONLY"


# 功能：验证只有 global_context 时只出现 Global section，其他 section 不出现
# 设计：只设置 global_context，断言 Project 和 Session 标题不在 prompt 中
def test_only_global() -> None:
    ctx = _make_ctx(global_context="global content")
    prompt = ctx.system_prompt("BASE")
    assert "## Global Context" in prompt
    assert "## Project Context" not in prompt
    assert "## Session Notes" not in prompt


# 功能：验证 session_notes 非空时包含 note_save 提示语
# 设计：只设置 session_notes，断言 prompt 含 note_save 相关提示
def test_session_notes_hint() -> None:
    ctx = _make_ctx(session_notes="some note")
    prompt = ctx.system_prompt("BASE")
    assert "note_save" in prompt
