from __future__ import annotations

from pathlib import Path

import pytest

from scott_claude.cli.commands.preset import cmd_preset_export, cmd_preset_validate
from scott_claude.core.agents.loader import AgentProfileLoader
from scott_claude.core.config import ScottConfig


# 功能：CLI 导出内建预设到指定路径并生成 Markdown 预设包
# 设计：cmd_preset_export 直写 -o 路径，断言文件含 scott_preset 头与源标记块
def test_cli_export_writes_package(tmp_path: Path) -> None:
    out = tmp_path / "planner.agent.md"
    cmd_preset_export("agent", "planner", str(out), ScottConfig())
    text = out.read_text(encoding="utf-8")
    assert 'scott_preset: "1.0"' in text
    assert "<!-- scott-preset-source:start -->" in text


# 功能：CLI 导出不存在的预设以 SystemExit(1) 结束
# 设计：捕获 SystemExit 断言退出码，验证错误路径不写文件
def test_cli_export_missing_exits(tmp_path: Path) -> None:
    out = tmp_path / "x.md"
    with pytest.raises(SystemExit) as exc:
        cmd_preset_export("agent", "no_such_preset_xyz", str(out), ScottConfig())
    assert exc.value.code == 1
    assert not out.exists()


# 功能：CLI 校验合法预设文件输出 OK 且不退出
# 设计：用内建 planner 源文件离线校验（KNOWN_TOOL_NAMES 近似注册表）
def test_cli_validate_ok(tmp_path: Path) -> None:
    src = AgentProfileLoader._BUILTIN_DIR / "planner.toml"
    cmd_preset_validate("agent", str(src), ScottConfig())


# 功能：CLI 校验非法文件以 SystemExit(1) 结束
# 设计：写坏 TOML 文件，断言退出码 1
def test_cli_validate_invalid_exits(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("[agent\nbroken", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        cmd_preset_validate("agent", str(bad), ScottConfig())
    assert exc.value.code == 1
