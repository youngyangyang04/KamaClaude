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


class PresetListParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kind: str = "all"  # "agent" | "skill" | "all"


class PresetListTool(BaseTool):
    params_model = PresetListParams
    name = "preset_list"
    description = (
        "List all agent presets and skills in the catalog with their tier "
        "(B=builtin, G=user global, L=project local) and description."
    )
    input_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["agent", "skill", "all"],
                "description": "Which catalog to list (default 'all').",
            },
        },
        "required": [],
    }

    # 生成 agent 预设目录行：[层级] 名称 — 描述
    def _agent_lines(self) -> list[str]:
        loader = AgentProfileLoader()
        builtin = AgentProfileLoader._BUILTIN_DIR
        global_dir = Path("~/.scott/agents").expanduser()
        local_dir = Path(".scott/agents")
        lines: list[str] = []
        for name in loader.list_all():
            path = loader.resolve_path(name)
            tier = tier_for(path, builtin, global_dir, local_dir) if path else "?"
            profile = loader.load(name)
            desc = profile.description if profile is not None else ""
            lines.append(f"[{tier}] {name} — {desc}")
        return lines

    # 生成 skill 目录行：[层级] 名称 — 描述
    def _skill_lines(self) -> list[str]:
        loader = SkillLoader()
        builtin = SkillLoader._BUILTIN_DIR
        global_dir = Path("~/.scott/skills").expanduser()
        local_dir = Path(".scott/skills")
        lines: list[str] = []
        for name in loader.list_all():
            path = loader.resolve_path(name)
            tier = tier_for(path, builtin, global_dir, local_dir) if path else "?"
            skill = loader.resolve(name)
            desc = skill.description if skill is not None else ""
            lines.append(f"[{tier}] {name} — {desc}")
        return lines

    # 按 kind 输出 agent/skill 目录
    async def invoke(self, params: dict[str, object]) -> ToolResult:
        p = PresetListParams.model_validate(params)
        sections: list[str] = []
        if p.kind in ("all", AGENT_KIND):
            sections.append("[agents]\n" + "\n".join(self._agent_lines()))
        if p.kind in ("all", SKILL_KIND):
            sections.append("[skills]\n" + "\n".join(self._skill_lines()))
        return ToolResult(content="\n\n".join(sections))
