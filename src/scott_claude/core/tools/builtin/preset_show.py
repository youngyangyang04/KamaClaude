from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from scott_claude.core.agents.loader import AgentProfileLoader
from scott_claude.core.skills.loader import SkillLoader
from scott_claude.core.tools.base import BaseTool, ToolResult
from scott_claude.core.tools.builtin.preset_common import (
    AGENT_KIND,
    SKILL_KIND,
    tier_for,
)

_DEFAULT_MAX_CHARS = 20_000


class PresetShowParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kind: str = AGENT_KIND
    name: str
    max_chars: int = _DEFAULT_MAX_CHARS


# 展示 agent 预设的解析结果 + 来源路径 + 原始内容
def _show_agent(loader: AgentProfileLoader, name: str, max_chars: int) -> str | None:
    path = loader.resolve_path(name)
    if path is None:
        return None
    profile = loader.load(name)
    if profile is None:
        return None
    builtin = AgentProfileLoader._BUILTIN_DIR
    tier = tier_for(path, builtin, Path("~/.scott/agents").expanduser(), Path(".scott/agents"))
    raw = path.read_text(encoding="utf-8")[:max_chars]
    return "\n".join(
        [
            "kind: agent",
            f"name: {profile.name}",
            f"tier: {tier}",
            f"path: {path}",
            f"description: {profile.description}",
            f"allowed_tools: {profile.allowed_tools}",
            f"model: {profile.model!r}",
            "",
            "--- raw source ---",
            raw,
        ]
    )


# 展示 skill 的解析结果 + 来源路径 + 原始内容
def _show_skill(loader: SkillLoader, name: str, max_chars: int) -> str | None:
    path = loader.resolve_path(name)
    if path is None:
        return None
    skill = loader.resolve(name)
    if skill is None:
        return None
    builtin = SkillLoader._BUILTIN_DIR
    tier = tier_for(path, builtin, Path("~/.scott/skills").expanduser(), Path(".scott/skills"))
    raw = path.read_text(encoding="utf-8")[:max_chars]
    return "\n".join(
        [
            "kind: skill",
            f"name: {skill.name}",
            f"tier: {tier}",
            f"path: {path}",
            f"description: {skill.description}",
            f"allowed_tools: {skill.allowed_tools}",
            "",
            "--- raw source ---",
            raw,
        ]
    )


class PresetShowTool(BaseTool):
    params_model = PresetShowParams
    name = "preset_show"
    description = (
        "Show a single agent preset or skill: resolved source path, tier, "
        "parsed fields and raw file content."
    )
    input_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["agent", "skill"],
                "description": "Catalog to look in (default 'agent').",
            },
            "name": {
                "type": "string",
                "description": "Preset or skill name (without extension).",
            },
            "max_chars": {
                "type": "integer",
                "description": "Cap on raw content returned (default 20000).",
            },
        },
        "required": ["name"],
    }

    # 按 kind 展示对应预设的解析结果与原始内容
    async def invoke(self, params: dict[str, object]) -> ToolResult:
        p = PresetShowParams.model_validate(params)
        if p.kind == AGENT_KIND:
            text = _show_agent(AgentProfileLoader(), p.name, p.max_chars)
        elif p.kind == SKILL_KIND:
            text = _show_skill(SkillLoader(), p.name, p.max_chars)
        else:
            return ToolResult(
                content=f"unknown kind: {p.kind!r}",
                is_error=True,
                error_type="schema_error",
            )
        if text is None:
            return ToolResult(
                content=f"preset not found: {p.kind}/{p.name}",
                is_error=True,
                error_type="runtime_error",
            )
        return ToolResult(content=text)
