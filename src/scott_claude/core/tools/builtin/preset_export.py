from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from scott_claude.core.agents.loader import AgentProfileLoader
from scott_claude.core.bus.events import PresetChangedEvent
from scott_claude.core.events.bus import EventBus
from scott_claude.core.skills.loader import SkillLoader
from scott_claude.core.tools.base import BaseTool, ToolResult
from scott_claude.core.tools.builtin.preset_common import (
    AGENT_KIND,
    SKILL_KIND,
    atomic_write_text,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


# 渲染预设为自包含 Markdown 预设包（统一 frontmatter + 元信息 + 原始内容标记块）
def render_export_markdown(
    kind: str,
    name: str,
    description: str,
    tools: list[str],
    model: str,
    raw: str,
) -> str:
    kind_label = "Agent 预设" if kind == AGENT_KIND else "Skill"
    header = "\n".join(
        [
            "---",
            'scott_preset: "1.0"',
            f"kind: {kind}",
            f"name: {name}",
            f"description: {description}",
            f"tools: {tools}",
            f'model: "{model}"',
            "---",
        ]
    )
    meta_rows = "\n".join(
        [
            f"| 名称 | {name} |",
            f"| 类型 | {kind} |",
            f"| 描述 | {description} |",
        ]
    )
    return "\n".join(
        [
            header,
            "",
            f"# {name}（{kind_label}）",
            "",
            "> 由 ScottClaude 导出 · 可导入回任意 ScottClaude 项目（`scott preset import <file>`）",
            "",
            "## 元信息",
            "",
            "| 字段 | 值 |",
            "| --- | --- |",
            meta_rows,
            "",
            "## 原始内容",
            "",
            "<!-- scott-preset-source:start -->",
            raw.rstrip("\n"),
            "<!-- scott-preset-source:end -->",
            "",
            "## 使用说明",
            "",
            "此文件由 `scott preset export` 生成，可直接阅读，或用 `scott preset import <file>` 还原到项目。",  # noqa: E501
            "",
        ]
    )


class PresetExportParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kind: str = AGENT_KIND
    name: str


class PresetExportTool(BaseTool):
    params_model = PresetExportParams
    name = "preset_export"
    description = (
        "Export an agent preset or skill as a self-contained, shareable Markdown "
        "package under ./workspace/. Safe: only writes inside ./workspace."
    )
    input_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["agent", "skill"],
                "description": "Catalog to export from (default 'agent').",
            },
            "name": {
                "type": "string",
                "description": "Preset or skill name (without extension).",
            },
        },
        "required": ["name"],
    }

    # 绑定事件总线与 run_id，导出成功后发布 preset.changed
    def __init__(self, bus: EventBus | None = None, run_id: str = "") -> None:
        self._bus = bus
        self._run_id = run_id

    # 解析指定预设并渲染导出到 ./workspace/，目标路径被工具强制限制
    async def invoke(self, params: dict[str, object]) -> ToolResult:
        p = PresetExportParams.model_validate(params)

        raw = ""
        desc = ""
        tools: list[str] = []
        model = ""
        if p.kind == AGENT_KIND:
            agent_loader = AgentProfileLoader()
            path = agent_loader.resolve_path(p.name)
            profile = agent_loader.load(p.name) if path is not None else None
            if path is None or profile is None:
                return ToolResult(
                    content=f"preset not found: agent/{p.name}",
                    is_error=True,
                    error_type="runtime_error",
                )
            raw = path.read_text(encoding="utf-8")
            desc = profile.description
            tools = profile.allowed_tools
            model = profile.model
        elif p.kind == SKILL_KIND:
            skill_loader = SkillLoader()
            path = skill_loader.resolve_path(p.name)
            skill = skill_loader.resolve(p.name) if path is not None else None
            if path is None or skill is None:
                return ToolResult(
                    content=f"preset not found: skill/{p.name}",
                    is_error=True,
                    error_type="runtime_error",
                )
            raw = path.read_text(encoding="utf-8")
            desc = skill.description
            tools = skill.allowed_tools
        else:
            return ToolResult(
                content=f"unknown kind: {p.kind!r}",
                is_error=True,
                error_type="schema_error",
            )

        markdown = render_export_markdown(p.kind, p.name, desc, tools, model, raw)
        target = Path("./workspace") / f"{p.name}.{p.kind}.md"
        atomic_write_text(target, markdown)

        if self._bus is not None:
            await self._bus.publish(
                PresetChangedEvent(
                    kind=p.kind,
                    name=p.name,
                    action="export",
                    tier="L",
                    path=str(target),
                    run_id=self._run_id,
                    ts=_now(),
                )
            )
        return ToolResult(
            content=f"exported: {target}\nShare this file or import it with "
            "`scott preset import <file>`."
        )
