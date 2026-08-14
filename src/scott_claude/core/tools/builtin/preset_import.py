from __future__ import annotations

import re
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
)
from scott_claude.core.tools.registry import ToolRegistry

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_SOURCE_RE = re.compile(
    r"<!-- scott-preset-source:start -->\n(.*?)<!-- scott-preset-source:end -->",
    re.DOTALL,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


# 解析导出包 frontmatter，返回 {kind, name}；非预设包返回 None
def _parse_package_frontmatter(text: str) -> dict[str, str] | None:
    m = _FRONTMATTER_RE.match(text)
    if m is None:
        return None
    fields: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip().strip('"').strip("'")
    if fields.get("scott_preset") != "1.0":
        return None
    if fields.get("kind") not in (AGENT_KIND, SKILL_KIND) or not fields.get("name"):
        return None
    return fields


# 从导出包提取标记块之间的原始预设内容；缺失返回 None
def _extract_source(text: str) -> str | None:
    m = _SOURCE_RE.search(text)
    if m is None:
        return None
    return m.group(1).rstrip("\n") + "\n"


class PresetImportParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    path: str
    target: str = "local"  # "local" | "global"


class PresetImportTool(BaseTool):
    params_model = PresetImportParams
    name = "preset_import"
    description = (
        "Import a preset package exported by preset_export (Markdown with "
        "scott_preset frontmatter) back into .scott/ or ~/.scott/. "
        "Validates before writing."
    )
    input_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the exported Markdown preset package.",
            },
            "target": {
                "type": "string",
                "enum": ["local", "global"],
                "description": "Write target: 'local' (.scott/) or 'global' (~/.scott/).",
            },
        },
        "required": ["path"],
    }

    # 绑定运行时注册表与事件总线，使校验能查工具名、导入后能发变更事件
    def __init__(
        self,
        registry: ToolRegistry,
        bus: EventBus | None = None,
        run_id: str = "",
    ) -> None:
        self._registry = registry
        self._bus = bus
        self._run_id = run_id

    # 解析导出包、校验并原子写入；失败不落盘
    async def invoke(self, params: dict[str, object]) -> ToolResult:
        p = PresetImportParams.model_validate(params)
        path = Path(p.path)
        if not path.exists() or not path.is_file():
            return ToolResult(
                content=f"file not found: {path}",
                is_error=True,
                error_type="runtime_error",
            )

        text = path.read_text(encoding="utf-8")
        fields = _parse_package_frontmatter(text)
        if fields is None:
            return ToolResult(
                content="not a valid preset package (missing scott_preset frontmatter)",
                is_error=True,
                error_type="schema_error",
            )
        content = _extract_source(text)
        if content is None:
            return ToolResult(
                content="preset package missing source markers",
                is_error=True,
                error_type="schema_error",
            )

        kind = fields["kind"]
        name = fields["name"]
        issues: list[PresetIssue] = list(validate_preset(kind, content, self._registry))
        if kind == SKILL_KIND:
            parsed = parse_skill_text(content)
            if parsed.name and parsed.name != name:
                issues.append(
                    PresetIssue(
                        "name",
                        f"frontmatter name {parsed.name!r} != package name {name!r}",
                    )
                )
        if issues:
            return ToolResult(
                content=format_issues(issues),
                is_error=True,
                error_type="schema_error",
            )

        base = Path("~/.scott").expanduser() if p.target == "global" else Path(".scott")
        if kind == AGENT_KIND:
            target = base / "agents" / f"{name}.toml"
        else:
            target = base / "skills" / f"{name}.md"
        atomic_write_text(target, content)

        if self._bus is not None:
            await self._bus.publish(
                PresetChangedEvent(
                    kind=kind,
                    name=name,
                    action="import",
                    tier="G" if p.target == "global" else "L",
                    path=str(target),
                    run_id=self._run_id,
                    ts=_now(),
                )
            )
        return ToolResult(
            content=f"imported: {target}\nTakes effect on the next run of this session."
        )
