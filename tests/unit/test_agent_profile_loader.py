from __future__ import annotations

from pathlib import Path

import pytest

from scott_claude.core.agents.loader import AgentProfileLoader


# 功能：内建 planner 角色配置应能被 AgentProfileLoader 加载
# 设计：直接调用 load("planner")，验证关键字段非空
def test_builtin_planner_found() -> None:
    loader = AgentProfileLoader()
    profile = loader.load("planner")
    assert profile is not None
    assert profile.name == "planner"
    assert profile.system_prompt != ""
    assert "read_file" in profile.allowed_tools or len(profile.allowed_tools) > 0


# 功能：内建三种角色均可加载
# 设计：参数化测试所有内建角色名
@pytest.mark.parametrize("role", ["planner", "executor", "reviewer"])
def test_all_builtin_roles_found(role: str) -> None:
    loader = AgentProfileLoader()
    profile = loader.load(role)
    assert profile is not None, f"builtin role '{role}' not found"
    assert profile.allowed_tools  # 每个内建角色都有 allowed_tools


# 功能：未知角色名应返回 None
# 设计：查找不存在的角色，断言返回 None 而非抛异常
def test_unknown_role_returns_none() -> None:
    loader = AgentProfileLoader()
    result = loader.load("nonexistent_role_xyz")
    assert result is None


# 功能：TOML 角色配置文件应被正确解析
# 设计：写入临时 TOML 文件，通过 _parse 解析并验证所有字段
def test_toml_parsed(tmp_path: Path) -> None:
    content = """\
[agent]
description = "测试角色"
system_prompt = "你是测试助手。"
allowed_tools = ["read_file", "bash"]
model = "claude-sonnet-4-6"
"""
    p = tmp_path / "tester.toml"
    p.write_text(content, encoding="utf-8")
    loader = AgentProfileLoader()
    profile = loader._parse(p, "tester")
    assert profile.name == "tester"
    assert profile.description == "测试角色"
    assert profile.system_prompt == "你是测试助手。"
    assert "read_file" in profile.allowed_tools
    assert "bash" in profile.allowed_tools
    assert profile.model == "claude-sonnet-4-6"


# 功能：项目本地角色配置应覆盖内建同名配置
# 设计：在 .scott/agents/ 中写入同名 TOML，monkeypatch cwd，断言加载到本地版本
def test_project_overrides_builtin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    local_agents = tmp_path / ".scott" / "agents"
    local_agents.mkdir(parents=True)
    (local_agents / "planner.toml").write_text(
        '[agent]\ndescription = "local planner"\nsystem_prompt = "local prompt"\n'
        'allowed_tools = ["list_dir"]\nmodel = ""\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    loader = AgentProfileLoader()
    profile = loader.load("planner")
    assert profile is not None
    assert profile.description == "local planner"
    assert "list_dir" in profile.allowed_tools
