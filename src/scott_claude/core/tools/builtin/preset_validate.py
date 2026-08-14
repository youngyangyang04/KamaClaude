from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from scott_claude.core.tools.base import BaseTool, ToolResult
from scott_claude.core.tools.builtin.preset_common import format_issues, validate_preset
from scott_claude.core.tools.registry import ToolRegistry


class PresetValidateParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kind: str
    text: str


class PresetValidateTool(BaseTool):
    params_model = PresetValidateParams
    name = "preset_validate"
    description = (
        "Validate a candidate agent preset (TOML) or skill (Markdown) without "
        "writing anything. Returns 'OK' or a list of field-level problems."
    )
    input_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["agent", "skill"],
                "description": "What the text is: 'agent' (TOML) or 'skill' (Markdown).",
            },
            "text": {
                "type": "string",
                "description": "Full preset text to validate.",
            },
        },
        "required": ["kind", "text"],
    }

    # 绑定运行时工具注册表，使校验能检查 allowed_tools 是否真实存在
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    # 对给定文本执行校验；有问题时以 schema_error 返回字段级清单
    async def invoke(self, params: dict[str, object]) -> ToolResult:
        p = PresetValidateParams.model_validate(params)
        issues = validate_preset(p.kind, p.text, self._registry)
        if issues:
            return ToolResult(
                content=format_issues(issues),
                is_error=True,
                error_type="schema_error",
            )
        return ToolResult(content="OK")
