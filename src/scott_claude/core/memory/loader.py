from __future__ import annotations

from pathlib import Path


# 读取指定路径的 context.md，路径不存在或内容为空时返回空字符串
def load_context_file(path: Path) -> str:
    p = path.expanduser()
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8").strip()
