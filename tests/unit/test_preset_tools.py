from __future__ import annotations

from pathlib import Path

import pytest

from scott_claude.core.agents.loader import AgentProfileLoader
from scott_claude.core.bus.events import PresetChangedEvent
from scott_claude.core.events.bus import EventBus
from scott_claude.core.skills.loader import SkillLoader
from scott_claude.core.tools.base import BaseTool, ToolResult
from scott_claude.core.tools.builtin.preset_common import validate_preset
from scott_claude.core.tools.builtin.preset_export import PresetExportTool
from scott_claude.core.tools.builtin.preset_import import PresetImportTool
from scott_claude.core.tools.builtin.preset_list import PresetListTool
from scott_claude.core.tools.builtin.preset_show import PresetShowTool
from scott_claude.core.tools.builtin.preset_validate import PresetValidateTool
from scott_claude.core.tools.builtin.preset_write import PresetWriteTool
from scott_claude.core.tools.registry import ToolRegistry


class _FakeTool(BaseTool):
    name = "fake"
    description = "fake"
    input_schema: dict[str, object] = {"type": "object", "properties": {}, "required": []}

    async def invoke(self, params: dict[str, object]) -> ToolResult:
        return ToolResult(content="ok")


# 构造带指定工具名的注册表，供校验引用
def _registry(*names: str) -> ToolRegistry:
    registry = ToolRegistry()
    for n in names:
        t = _FakeTool()
        t.name = n
        registry.register(t)
    return registry


_VALID_AGENT = """\
[agent]
description = "测试角色"
system_prompt = "你是测试助手。"
allowed_tools = ["bash", "read_file"]
"""

_VALID_SKILL = """\
---
name: demo
description: 演示 skill
allowed_tools:
  - bash
---
请执行：$ARGUMENTS
"""


# 功能：合法 agent TOML 通过校验，问题列表为空
# 设计：用真实可解析的 TOML + 注册表内的工具名，验证主路径返回空列表而非抛异常
def test_validate_agent_ok() -> None:
    issues = validate_preset("agent", _VALID_AGENT, _registry("bash", "read_file"))
    assert issues == []


# 功能：坏 TOML 返回 toml 字段级错误
# 设计：喂语法错误的文本，验证不抛异常而是返回结构化问题
def test_validate_agent_bad_toml() -> None:
    issues = validate_preset("agent", "[agent\nbad", _registry("bash"))
    assert any(i.field == "toml" for i in issues)


# 功能：缺失 [agent] 表返回 agent 字段错误
# 设计：用只有无关键的 TOML，验证缺表被识别
def test_validate_agent_missing_table() -> None:
    issues = validate_preset("agent", "other = 1", _registry("bash"))
    assert any(i.field == "agent" for i in issues)


# 功能：空 description / system_prompt 被判为必填缺失
# 设计：字段存在但为空串，验证非空校验生效
def test_validate_agent_empty_required_fields() -> None:
    text = '[agent]\ndescription = ""\nsystem_prompt = "   "\n'
    issues = validate_preset("agent", text, _registry("bash"))
    fields = {i.field for i in issues}
    assert "description" in fields
    assert "system_prompt" in fields


# 功能：allowed_tools 引用未注册工具被拒绝
# 设计：注册表只有 bash，文本引用 bash + ghost，验证仅 ghost 报错
def test_validate_agent_unknown_tool() -> None:
    text = _VALID_AGENT.replace('"bash", "read_file"', '"bash", "ghost"')
    issues = validate_preset("agent", text, _registry("bash", "read_file"))
    assert any(i.field == "allowed_tools" and "ghost" in i.message for i in issues)


# 功能：model 非字符串被判为类型错误
# 设计：model 给整数，验证 model 字段报错
def test_validate_agent_model_type() -> None:
    text = _VALID_AGENT + 'model = 123\n'
    issues = validate_preset("agent", text, _registry("bash", "read_file"))
    assert any(i.field == "model" for i in issues)


# 功能：合法 skill Markdown 通过校验
# 设计：带 frontmatter 与正文的 skill，工具名在注册表内，验证返回空列表
def test_validate_skill_ok() -> None:
    issues = validate_preset("skill", _VALID_SKILL, _registry("bash"))
    assert issues == []


# 功能：frontmatter 缺 name 被判为缺失
# 设计：仅缺 name 字段的 skill，验证 name 字段报错且其余正常
def test_validate_skill_missing_name() -> None:
    text = _VALID_SKILL.replace("name: demo\n", "")
    issues = validate_preset("skill", text, _registry("bash"))
    assert any(i.field == "name" for i in issues)


# 功能：skill 引用未注册工具被拒绝
# 设计：allowed_tools 引用 ghost，验证报错
def test_validate_skill_unknown_tool() -> None:
    text = _VALID_SKILL.replace("- bash", "- ghost")
    issues = validate_preset("skill", text, _registry("bash"))
    assert any(i.field == "allowed_tools" and "ghost" in i.message for i in issues)


# 功能：未知 kind 返回 kind 字段错误
# 设计：传 "module"，验证不抛异常且报 unknown kind
def test_validate_unknown_kind() -> None:
    issues = validate_preset("module", _VALID_AGENT, _registry("bash"))
    assert any(i.field == "kind" for i in issues)


# 功能：registry.names() 返回全部已注册工具名
# 设计：注册两个工具，断言集合相等（顺序无关）
def test_registry_names() -> None:
    registry = _registry("bash", "read_file")
    assert set(registry.names()) == {"bash", "read_file"}


# 功能：preset_validate 工具对合法文本返回 OK
# 设计：直接 invoke 工具而非底层函数，验证工具层返回值
async def test_preset_validate_tool_ok() -> None:
    tool = PresetValidateTool(_registry("bash", "read_file"))
    result = await tool.invoke({"kind": "agent", "text": _VALID_AGENT})
    assert not result.is_error
    assert result.content == "OK"


# 功能：preset_validate 工具对非法文本返回 schema_error
# 设计：文本含未知工具，验证 is_error 与字段级消息
async def test_preset_validate_tool_rejects() -> None:
    tool = PresetValidateTool(_registry("bash"))
    text = _VALID_AGENT.replace('"bash", "read_file"', '"bash", "ghost"')
    result = await tool.invoke({"kind": "agent", "text": text})
    assert result.is_error
    assert result.error_type == "schema_error"
    assert "ghost" in result.content


# 功能：preset_list 能列出内建 planner 角色并带 B 层级标记
# 设计：在干净环境列出 agent 目录，断言 planner 出现且行首为 [B]
async def test_preset_list_contains_builtin_agents() -> None:
    tool = PresetListTool()
    result = await tool.invoke({"kind": "agent"})
    assert "planner" in result.content
    assert "[B] planner" in result.content


# 功能：preset_show 能展示内建 planner 的来源与解析字段
# 设计：show planner，断言输出包含 kind/tier/path/system_prompt 关键信息
async def test_preset_show_builtin_planner() -> None:
    tool = PresetShowTool()
    result = await tool.invoke({"kind": "agent", "name": "planner"})
    assert not result.is_error
    assert "kind: agent" in result.content
    assert "tier: B" in result.content
    assert "[agent]" in result.content


# 功能：preset_show 对不存在的预设返回错误
# 设计：查询随机不存在的名字，验证返回 runtime_error
async def test_preset_show_missing() -> None:
    tool = PresetShowTool()
    result = await tool.invoke({"kind": "agent", "name": "no_such_preset_xyz"})
    assert result.is_error
    assert result.error_type == "runtime_error"


# 功能：项目本地预设覆盖内建并标记为 L 层级
# 设计：在 .scott/agents/ 写入同名 TOML 后 chdir，断言 list/show 看到 L 层级本地版本
async def test_project_local_overrides_builtin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    local = tmp_path / ".scott" / "agents"
    local.mkdir(parents=True)
    (local / "planner.toml").write_text(
        '[agent]\ndescription = "local planner"\nsystem_prompt = "local prompt"\n'
        'allowed_tools = ["read_file"]\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    tool = PresetListTool()
    result = await tool.invoke({"kind": "agent"})
    assert "[L] planner — local planner" in result.content


_NEW_AGENT = """\
[agent]
description = "新角色"
system_prompt = "你是新角色。"
allowed_tools = ["read_file"]
"""


# 功能：preset_write 将合法 agent 预设写入项目本地 .scott/agents/
# 设计：chdir 到临时目录后写入，断言文件存在、内容一致、无残留临时文件
async def test_preset_write_agent_local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    tool = PresetWriteTool(_registry("read_file"))
    result = await tool.invoke({"kind": "agent", "name": "newrole", "content": _NEW_AGENT})
    assert not result.is_error
    target = tmp_path / ".scott" / "agents" / "newrole.toml"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == _NEW_AGENT
    assert list((tmp_path / ".scott" / "agents").glob("*.tmp")) == []


# 功能：preset_write 校验失败时拒绝落盘且不产生文件
# 设计：给坏 TOML 与未知工具两种非法内容，断言返回 schema_error 且目标文件不存在
async def test_preset_write_rejects_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    tool = PresetWriteTool(_registry("read_file"))
    bad = await tool.invoke({"kind": "agent", "name": "bad", "content": "[agent\nbroken"})
    assert bad.is_error
    assert bad.error_type == "schema_error"
    unknown = await tool.invoke(
        {"kind": "agent", "name": "ghost", "content": _NEW_AGENT.replace("read_file", "ghost")}
    )
    assert unknown.is_error
    assert not (tmp_path / ".scott" / "agents").exists()


# 功能：skill frontmatter name 与写入名不一致时被拒绝
# 设计：frontmatter 声明 name: other 而请求写 demo，断言报 name 字段错且不落盘
async def test_preset_write_skill_name_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    tool = PresetWriteTool(_registry("bash"))
    content = _VALID_SKILL.replace("name: demo", "name: other")
    result = await tool.invoke({"kind": "skill", "name": "demo", "content": content})
    assert result.is_error
    assert "other" in result.content
    assert not (tmp_path / ".scott" / "skills").exists()


# 功能：preset_write 的 target=global 写入用户目录 ~/.scott/
# 设计：monkeypatch USERPROFILE/HOME 指向临时目录，断言写入了 ~/.scott/agents/
async def test_preset_write_global(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    tool = PresetWriteTool(_registry("read_file"))
    result = await tool.invoke(
        {"kind": "agent", "name": "globalrole", "content": _NEW_AGENT, "target": "global"}
    )
    assert not result.is_error
    assert (tmp_path / ".scott" / "agents" / "globalrole.toml").exists()


# 功能：preset_write 成功后向总线发布 PresetChangedEvent
# 设计：注入 EventBus 并订阅收集，断言事件含 kind/name/action/tier/path 与 run_id
async def test_preset_write_publishes_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    bus = EventBus()
    events: list[PresetChangedEvent] = []

    async def _collect(event: object) -> None:
        if isinstance(event, PresetChangedEvent):
            events.append(event)

    bus.subscribe(_collect)
    tool = PresetWriteTool(_registry("read_file"), bus=bus, run_id="run-1")
    await tool.invoke({"kind": "agent", "name": "newrole", "content": _NEW_AGENT})
    assert len(events) == 1
    ev = events[0]
    assert ev.kind == "agent"
    assert ev.name == "newrole"
    assert ev.action == "write"
    assert ev.tier == "L"
    assert ev.run_id == "run-1"


# 功能：preset_write 拒绝含路径穿越的预设名
# 设计：name 带 ".."，断言返回 schema_error
async def test_preset_write_rejects_traversal_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    tool = PresetWriteTool(_registry("read_file"))
    result = await tool.invoke({"kind": "agent", "name": "../evil", "content": _NEW_AGENT})
    assert result.is_error
    assert not (tmp_path / ".scott" / "agents").exists()


# 功能：内建 creator 预设可解析且自带预设工具集
# 设计：加载 creator profile，断言关键字段与 preset_* 工具都在 allowed_tools 中
def test_creator_profile_builtin() -> None:
    profile = AgentProfileLoader().load("creator")
    assert profile is not None
    assert "创作" in profile.description or "预设" in profile.description
    for tool in ["preset_list", "preset_show", "preset_validate", "preset_write", "preset_export"]:
        assert tool in profile.allowed_tools


# 功能：内建创作技能 author-preset / author-skill 均可解析
# 设计：解析两个技能，断言 frontmatter 字段完整且正文含 $ARGUMENTS
@pytest.mark.parametrize("name", ["author-preset", "author-skill"])
def test_author_skills_builtin(name: str) -> None:
    skill = SkillLoader().resolve(name)
    assert skill is not None
    assert skill.description != ""
    assert "$ARGUMENTS" in skill.system_prompt_template
    assert "preset_validate" in skill.allowed_tools


# 功能：preset_export 将内建预设导出为带标记的 Markdown 包到 ./workspace/
# 设计：导出 planner，断言文件存在、frontmatter 带 scott_preset 版本头、含源标记块
async def test_preset_export_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    tool = PresetExportTool()
    result = await tool.invoke({"kind": "agent", "name": "planner"})
    assert not result.is_error
    target = tmp_path / "workspace" / "planner.agent.md"
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert 'scott_preset: "1.0"' in text
    assert "<!-- scott-preset-source:start -->" in text
    assert "<!-- scott-preset-source:end -->" in text
    assert "[agent]" in text


# 功能：preset_export 对不存在的预设返回错误
# 设计：导出随机名字，断言返回 runtime_error 且不产生文件
async def test_preset_export_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    tool = PresetExportTool()
    result = await tool.invoke({"kind": "agent", "name": "no_such_preset_xyz"})
    assert result.is_error
    assert result.error_type == "runtime_error"


# 功能：导出 → 导入往返后，还原内容与源语义一致并成为项目本地预设
# 设计：导出内建 planner，再导入到临时项目，断言内容逐字一致且 list 标记为 [L]
async def test_export_import_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _registry("read_file", "list_dir", "task_create", "task_update", "bash")

    export_result = await PresetExportTool().invoke({"kind": "agent", "name": "planner"})
    assert not export_result.is_error

    import_result = await PresetImportTool(registry).invoke(
        {"path": str(tmp_path / "workspace" / "planner.agent.md")}
    )
    assert not import_result.is_error, import_result.content

    target = tmp_path / ".scott" / "agents" / "planner.toml"
    assert target.exists()
    original = AgentProfileLoader._BUILTIN_DIR / "planner.toml"
    assert target.read_text(encoding="utf-8") == original.read_text(encoding="utf-8")

    listed = await PresetListTool().invoke({"kind": "agent"})
    assert "[L] planner" in listed.content


# 功能：preset_import 拒绝无 scott_preset 头的普通 Markdown
# 设计：写一个普通 md 文件导入，断言返回 schema_error
async def test_preset_import_rejects_plain_md(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    plain = tmp_path / "plain.md"
    plain.write_text("# 随便一个文档\n", encoding="utf-8")
    result = await PresetImportTool(_registry("bash")).invoke({"path": str(plain)})
    assert result.is_error
    assert result.error_type == "schema_error"


# 功能：preset_import 对不存在的文件返回错误
# 设计：导入随机路径，断言返回 runtime_error
async def test_preset_import_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = await PresetImportTool(_registry("bash")).invoke({"path": "no/such/file.md"})
    assert result.is_error
    assert result.error_type == "runtime_error"
