from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from scott_claude.core.bus.events import PresetChangedEvent
from scott_claude.core.events.bus import EventBus
from scott_claude.core.skills.loader import parse_skill_text
from scott_claude.core.tools.base import BaseTool, ToolResult
from scott_claude.core.tools.builtin.preset_common import (
    AGENT_KIND,
    SKILL_KIND,
    PresetIssue,
    atomic_write_text,
    format_issues,
    validate_preset,
    validate_preset_name,
)
from scott_claude.core.tools.registry import ToolRegistry


def _now() -> str:
    return datetime.now(UTC).isoformat()


class PresetWriteParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kind: str
    name: str
    content: str
    target: str = "local"  # "local" | "global"


class PresetWriteTool(BaseTool):
    params_model = PresetWriteParams
    name = "preset_write"
    description = (
        "Validate and write a new agent preset (TOML) or skill (Markdown) into "
        ".scott/ (project local, default) or ~/.scott/ (user global). Takes "
        "effect on the next run of this session. Never writes builtin presets."
    )
    input_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["agent", "skill"],
                "description": "What to write: 'agent' (TOML) or 'skill' (Markdown).",
            },
            "name": {
                "type": "string",
                "description": "Preset name (no extension, no path separators).",
            },
            "content": {
                "type": "string",
                "description": "Full preset content to validate and write.",
            },
            "target": {
                "type": "string",
                "enum": ["local", "global"],
                "description": "Write target: 'local' (.scott/) or 'global' (~/.scott/).",
            },
        },
        "required": ["kind", "name", "content"],
    }

    # 绑定运行时注册表与事件总线，使校验能查工具名、写盘后能发变更事件
    def __init__(
        self,
        registry: ToolRegistry,
        bus: EventBus | None = None,
        run_id: str = "",
    ) -> None:
        self._registry = registry
        self._bus = bus
        self._run_id = run_id

    # 校验并原子写入预设；校验失败不落盘、不发事件
    async def invoke(self, params: dict[str, object]) -> ToolResult:
        p = PresetWriteParams.model_validate(params)

        issues: list[PresetIssue] = []
        name_issue = validate_preset_name(p.name)
        if name_issue is not None:
            issues.append(name_issue)
        issues.extend(validate_preset(p.kind, p.content, self._registry))

        # skill 的 frontmatter name 若声明，必须与写入文件名一致
        if p.kind == SKILL_KIND:
            parsed = parse_skill_text(p.content)
            if parsed.name and parsed.name != p.name:
                issues.append(
                    PresetIssue("name", f"frontmatter name {parsed.name!r} != requested {p.name!r}")
                )

        if issues:
            return ToolResult(
                content=format_issues(issues),
                is_error=True,
                error_type="schema_error",
            )

        base = Path("~/.scott").expanduser() if p.target == "global" else Path(".scott")
        if p.kind == AGENT_KIND:
            target = base / "agents" / f"{p.name}.toml"
        else:
            target = base / "skills" / f"{p.name}.md"
        atomic_write_text(target, p.content)

        if self._bus is not None:
            await self._bus.publish(
                PresetChangedEvent(
                    kind=p.kind,
                    name=p.name,
                    action="write",
                    tier="G" if p.target == "global" else "L",
                    path=str(target),
                    run_id=self._run_id,
                    ts=_now(),
                )
            )
        return ToolResult(
            content=f"written: {target}\n"
            "Takes effect on the next run of this session."
        )
