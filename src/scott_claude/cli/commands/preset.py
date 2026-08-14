from __future__ import annotations

import asyncio
import sys
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

from scott_claude.core.agents.loader import AgentProfileLoader
from scott_claude.core.config import ScottConfig
from scott_claude.core.skills.loader import SkillLoader
from scott_claude.core.tools.base import ToolResult
from scott_claude.core.tools.builtin.preset_common import (
    AGENT_KIND,
    SKILL_KIND,
    atomic_write_text,
    catalog_registry,
    format_issues,
    validate_preset,
)
from scott_claude.core.tools.builtin.preset_export import render_export_markdown
from scott_claude.core.tools.builtin.preset_import import PresetImportTool
from scott_claude.core.tools.builtin.preset_list import PresetListTool
from scott_claude.core.tools.builtin.preset_show import PresetShowTool
from scott_claude.core.tools.registry import ToolRegistry


# 运行异步工具调用并打印结果；工具报错时以退出码 1 结束
def _invoke(coro: Coroutine[Any, Any, ToolResult]) -> None:
    result = asyncio.run(coro)
    print(result.content)
    if result.is_error:
        sys.exit(1)


# scott preset list：列出 agent/skill 目录（B/G/L 层级 + 描述）
def cmd_preset_list(kind: str, config: ScottConfig) -> None:
    _invoke(PresetListTool().invoke({"kind": kind}))


# scott preset show：展示单个预设的解析结果与原始内容
def cmd_preset_show(kind: str, name: str, config: ScottConfig) -> None:
    _invoke(PresetShowTool().invoke({"kind": kind, "name": name}))


# scott preset validate：离线校验预设文件（用内建工具名全集近似注册表）
def cmd_preset_validate(kind: str, file: str, config: ScottConfig) -> None:
    path = Path(file)
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        sys.exit(1)
    text = path.read_text(encoding="utf-8")
    issues = validate_preset(kind, text, catalog_registry())
    if issues:
        print(format_issues(issues), file=sys.stderr)
        sys.exit(1)
    print("OK")


# 生成 agent 预设模板文本
def _agent_template(name: str) -> str:
    return (
        "[agent]\n"
        'description = "（写一句话：这个角色的职责与边界）"\n'
        'system_prompt = """\n'
        "（写完整的行为规范：职责、原则、输出格式）\n"
        '"""\n'
        'allowed_tools = ["read_file", "list_dir"]\n'
        'model = ""\n'
    )


# 生成 skill 模板文本
def _skill_template(name: str) -> str:
    return (
        "---\n"
        f"name: {name}\n"
        "description: （写一句话：何时用、解决什么）\n"
        "allowed_tools:\n"
        "  - read_file\n"
        "---\n"
        "（写 system prompt：执行步骤 + 汇报格式，可用 $ARGUMENTS 接收参数）\n"
    )


# scott preset new：在 .scott/ 生成一个可编辑的预设模板
def cmd_preset_new(name: str, kind: str, config: ScottConfig) -> None:
    if kind == AGENT_KIND:
        content = _agent_template(name)
        target = Path(".scott") / "agents" / f"{name}.toml"
    elif kind == SKILL_KIND:
        content = _skill_template(name)
        target = Path(".scott") / "skills" / f"{name}.md"
    else:
        print(f"unknown kind: {kind!r}", file=sys.stderr)
        sys.exit(1)
    atomic_write_text(target, content)
    print(f"created: {target}  (edit it, then `scott preset validate {kind} {target}`)")


# scott preset export：把预设渲染为可分享的 Markdown 预设包
def cmd_preset_export(
    kind: str, name: str, out: str | None, config: ScottConfig
) -> None:
    path: Path | None = None
    desc = ""
    tools: list[str] = []
    model = ""
    if kind == AGENT_KIND:
        agent_loader = AgentProfileLoader()
        path = agent_loader.resolve_path(name)
        profile = agent_loader.load(name) if path is not None else None
        if profile is None:
            print(f"preset not found: agent/{name}", file=sys.stderr)
            sys.exit(1)
        desc, tools, model = profile.description, profile.allowed_tools, profile.model
    elif kind == SKILL_KIND:
        skill_loader = SkillLoader()
        path = skill_loader.resolve_path(name)
        skill = skill_loader.resolve(name) if path is not None else None
        if skill is None:
            print(f"preset not found: skill/{name}", file=sys.stderr)
            sys.exit(1)
        desc, tools = skill.description, skill.allowed_tools
    else:
        print(f"unknown kind: {kind!r}", file=sys.stderr)
        sys.exit(1)

    assert path is not None
    raw = path.read_text(encoding="utf-8")
    markdown = render_export_markdown(kind, name, desc, tools, model, raw)
    target = Path(out) if out else Path("./workspace") / f"{name}.{kind}.md"
    atomic_write_text(target, markdown)
    print(f"exported: {target}")


# scott preset import：导入 Markdown 预设包（还原写入 .scott/ 或 ~/.scott/）
def cmd_preset_import(file: str, global_: bool, config: ScottConfig) -> None:
    registry: ToolRegistry = catalog_registry()
    _invoke(
        PresetImportTool(registry).invoke(
            {"path": file, "target": "global" if global_ else "local"}
        )
    )
