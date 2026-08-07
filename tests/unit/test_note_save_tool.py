from __future__ import annotations

from pathlib import Path

from scott_claude.core.session.store import SessionStore
from scott_claude.core.tools.builtin.note_save import NoteSaveTool


# 功能：验证 note_save 正常调用会把 content 写入 notes.md
# 设计：使用真实 SessionStore 和 tmp_path，断言工具返回与文件内容，覆盖工具到文件层的完整路径
async def test_note_save_appends_note(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    tool = NoteSaveTool(store, "sess-1", "run-1")

    result = await tool.invoke({"content": "Python 3.12"})

    assert result.content == "saved"
    assert not result.is_error
    assert "Python 3.12" in store.read_notes("sess-1")


# 功能：验证空 content 会返回工具错误且不写入 notes.md
# 设计：传入空白字符串，断言 is_error 与 error_type，覆盖 schema 之外的业务校验
async def test_note_save_rejects_empty_content(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    tool = NoteSaveTool(store, "sess-1", "run-1")

    result = await tool.invoke({"content": "   "})

    assert result.is_error
    assert result.error_type == "runtime_error"
    assert store.read_notes("sess-1") == ""
