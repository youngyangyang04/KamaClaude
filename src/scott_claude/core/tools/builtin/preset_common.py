from __future__ import annotations

import os
import tomllib
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from scott_claude.core.skills.loader import parse_skill_text
from scott_claude.core.tools.base import BaseTool, ToolResult
from scott_claude.core.tools.registry import ToolRegistry

AGENT_KIND = "agent"
SKILL_KIND = "skill"
KINDS = (AGENT_KIND, SKILL_KIND)

# 按层级标记预设来源：B=内建 G=用户全局 L=项目本地
TIER_BUILTIN = "B"
TIER_GLOBAL = "G"
TIER_LOCAL = "L"


@dataclass
class PresetIssue:
    field: str
    message: str


# 校验 agent TOML 文本：表结构、必填字段、工具名可解析、model 类型
def _validate_agent(text: str, registry: ToolRegistry) -> list[PresetIssue]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return [PresetIssue("toml", f"invalid TOML: {exc}")]

    agent = data.get("agent")
    if not isinstance(agent, dict):
        return [PresetIssue("agent", "missing [agent] table")]

    issues: list[PresetIssue] = []
    desc = agent.get("description")
    if not isinstance(desc, str) or not desc.strip():
        issues.append(PresetIssue("description", "must be a non-empty string"))

    prompt = agent.get("system_prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        issues.append(PresetIssue("system_prompt", "must be a non-empty string"))

    tools = agent.get("allowed_tools", [])
    if not isinstance(tools, list):
        issues.append(PresetIssue("allowed_tools", "must be a list of tool names"))
    else:
        known = set(registry.names())
        for t in tools:
            if not isinstance(t, str):
                issues.append(PresetIssue("allowed_tools", f"entry must be a string: {t!r}"))
            elif t not in known:
                issues.append(PresetIssue("allowed_tools", f"unknown tool: {t!r}"))

    model = agent.get("model")
    if model is not None and not isinstance(model, str):
        issues.append(PresetIssue("model", "must be a string"))

    return issues


# 校验 skill Markdown 文本：frontmatter、必填字段、工具名可解析
def _validate_skill(text: str, registry: ToolRegistry) -> list[PresetIssue]:
    issues: list[PresetIssue] = []
    skill = parse_skill_text(text)

    if not skill.name:
        issues.append(PresetIssue("name", "frontmatter must declare name:"))

    if not skill.description.strip():
        issues.append(
            PresetIssue("description", "frontmatter must declare a non-empty description")
        )

    known = set(registry.names())
    for t in skill.allowed_tools:
        if t not in known:
            issues.append(PresetIssue("allowed_tools", f"unknown tool: {t!r}"))

    if not skill.system_prompt_template.strip():
        issues.append(PresetIssue("system_prompt", "skill body must be non-empty"))

    return issues


# 校验预设文本（agent TOML 或 skill Markdown），返回问题列表；空列表表示通过
def validate_preset(kind: str, text: str, registry: ToolRegistry) -> list[PresetIssue]:
    if kind == AGENT_KIND:
        return _validate_agent(text, registry)
    if kind == SKILL_KIND:
        return _validate_skill(text, registry)
    return [PresetIssue("kind", f"unknown kind: {kind!r} (expected 'agent' | 'skill')")]


# 格式化问题列表为多行字符串，供工具返回给模型
def format_issues(issues: list[PresetIssue]) -> str:
    return "\n".join(f"- {i.field}: {i.message}" for i in issues)


# 判断路径落在哪个层级目录之下：L/G/B，无法识别返回 "?"
def tier_for(path: Path, builtin_dir: Path, global_dir: Path, local_dir: Path) -> str:
    for tier, d in (
        (TIER_LOCAL, local_dir),
        (TIER_GLOBAL, global_dir),
        (TIER_BUILTIN, builtin_dir),
    ):
        try:
            path.resolve().relative_to(d.expanduser().resolve())
            return tier
        except ValueError:
            continue
    return "?"


# 校验预设名：非空、无路径分隔符、不以点开头，防止路径穿越
def validate_preset_name(name: str) -> PresetIssue | None:
    if not name:
        return PresetIssue("name", "must be non-empty")
    if name in (".", "..") or "/" in name or "\\" in name or name.startswith("."):
        return PresetIssue("name", f"invalid preset name: {name!r}")
    return None


# 原子写入文本文件：同目录唯一临时文件 + os.replace，避免 loader 读到半截内容
def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# 内建工具名全集：CLI 离线校验时作为注册表近似（会话内以真实注册表为准）
KNOWN_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "read_file",
        "bash",
        "write_file",
        "list_dir",
        "note_save",
        "task_create",
        "task_update",
        "task_list",
        "task_get",
        "spawn_agent",
        "agent_result",
        "preset_list",
        "preset_show",
        "preset_validate",
        "preset_write",
        "preset_export",
        "preset_import",
    }
)


class _CatalogProbeTool(BaseTool):
    input_schema: dict[str, object] = {"type": "object", "properties": {}, "required": []}
    description = "catalog probe for offline validation"

    # 探针工具只需占位工具名，invoke 永不执行
    def __init__(self, name: str) -> None:
        self.name = name

    # 返回空结果，仅满足 BaseTool 抽象接口
    async def invoke(self, params: dict[str, object]) -> ToolResult:
        return ToolResult(content="")


# 用给定工具名集合构造一个仅用于离线校验的注册表
def catalog_registry(names: Iterable[str] = KNOWN_TOOL_NAMES) -> ToolRegistry:
    registry = ToolRegistry()
    for n in names:
        registry.register(_CatalogProbeTool(n))
    return registry
