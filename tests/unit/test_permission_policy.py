from __future__ import annotations

from scott_claude.core.permissions.policy import (
    PermissionDecision,
    ToolPolicy,
    evaluate,
    matches_outside_cwd,
    param_preview,
)

# ── Tier 1: deny_patterns ────────────────────────────────────────────────────

# 功能：验证 deny_patterns 命中时直接返回 DENY，不继续检查后续层
# 设计：配置 deny 模式 "rm\s+-rf"，传入匹配命令；DENY 在最高优先级，阻止危险命令
def test_deny_pattern_wins() -> None:
    policy = ToolPolicy(
        default=PermissionDecision.ASK,
        deny_patterns=[r"rm\s+-rf"],
    )
    result = evaluate("bash", {"command": "rm -rf /tmp"}, policy)
    assert result == PermissionDecision.DENY


# 功能：验证 deny_patterns 不匹配时不影响后续层
# 设计：配置 deny 模式 "rm"，传入不含 rm 的命令；确认不会误拦截
def test_deny_pattern_no_match_falls_through() -> None:
    policy = ToolPolicy(
        default=PermissionDecision.ASK,
        deny_patterns=[r"\brm\b"],
        allow_patterns=[r"echo"],
    )
    result = evaluate("bash", {"command": "echo hi"}, policy)
    assert result == PermissionDecision.ALLOW


# ── Tier 2: OUTSIDE_CWD_HEURISTICS ───────────────────────────────────────────

# 功能：验证绝对路径命令触发 OUTSIDE_CWD 强制 ASK，即使 allow_patterns 也包含它
# 设计：核心安全约束——allow_patterns 在第 3 层，OUTSIDE_CWD 在第 2 层，越界命令不可被静默放行
def test_outside_cwd_absolute_path_forces_ask() -> None:
    policy = ToolPolicy(
        default=PermissionDecision.ASK,
        allow_patterns=[r".*"],  # "allow everything" — should not bypass OUTSIDE_CWD
    )
    result = evaluate("bash", {"command": "cat /etc/hosts"}, policy)
    assert result == PermissionDecision.ASK


# 功能：验证 ~ 开头路径触发 OUTSIDE_CWD 强制 ASK
# 设计：~ 展开指向 home 目录，超出 cwd 范围，必须经用户确认
def test_outside_cwd_tilde_forces_ask() -> None:
    policy = ToolPolicy(default=PermissionDecision.ASK, allow_patterns=[r".*"])
    result = evaluate("bash", {"command": "ls ~/Documents"}, policy)
    assert result == PermissionDecision.ASK


# 功能：验证 .. 路径遍历触发 OUTSIDE_CWD 强制 ASK
# 设计：../sibling 越出 cwd，即使 allow_patterns 匹配也必须询问
def test_outside_cwd_parent_traversal_forces_ask() -> None:
    policy = ToolPolicy(default=PermissionDecision.ASK, allow_patterns=[r".*"])
    result = evaluate("bash", {"command": "ls ../sibling"}, policy)
    assert result == PermissionDecision.ASK


# 功能：验证 $HOME 变量触发 OUTSIDE_CWD 强制 ASK
# 设计：$HOME 是绝对路径的间接引用，与直接写 /home/user/ 同等风险
def test_outside_cwd_dollar_home_forces_ask() -> None:
    policy = ToolPolicy(default=PermissionDecision.ASK, allow_patterns=[r".*"])
    result = evaluate("bash", {"command": "echo $HOME"}, policy)
    assert result == PermissionDecision.ASK


# 功能：验证 cd 命令触发 OUTSIDE_CWD 强制 ASK
# 设计：cd 改变工作目录，后续相对路径操作可能越出 cwd，属于高风险操作
def test_outside_cwd_cd_forces_ask() -> None:
    policy = ToolPolicy(default=PermissionDecision.ASK, allow_patterns=[r".*"])
    result = evaluate("bash", {"command": "cd /tmp && ls"}, policy)
    assert result == PermissionDecision.ASK


# 功能：验证纯相对路径命令不触发 OUTSIDE_CWD
# 设计：echo hi / ls src/ 等安全命令应正常走 allow_patterns 或 default 层
def test_relative_path_not_outside_cwd() -> None:
    assert not matches_outside_cwd("echo hello")
    assert not matches_outside_cwd("ls src/")
    assert not matches_outside_cwd("cat README.md")
    assert not matches_outside_cwd("python -m pytest")


# 功能：验证 deny_patterns 优先于 OUTSIDE_CWD（deny 在 tier 1，先检查）
# 设计：命令同时命中 deny_patterns 和 outside-cwd，结果应为 DENY 而非 ASK
def test_deny_wins_over_outside_cwd() -> None:
    policy = ToolPolicy(
        default=PermissionDecision.ASK,
        deny_patterns=[r"rm\s+-rf"],
    )
    result = evaluate("bash", {"command": "rm -rf /tmp"}, policy)
    assert result == PermissionDecision.DENY


# ── Tier 3: allow_patterns ───────────────────────────────────────────────────

# 功能：验证 allow_patterns 命中时返回 ALLOW（在 OUTSIDE_CWD 未命中的前提下）
# 设计：echo 是安全的本地命令，配置 allow_patterns 后不需要用户审批
def test_allow_pattern_grants_access() -> None:
    policy = ToolPolicy(
        default=PermissionDecision.ASK,
        allow_patterns=[r"^echo\b"],
    )
    result = evaluate("bash", {"command": "echo hello"}, policy)
    assert result == PermissionDecision.ALLOW


# ── Tier 4: tool defaults ─────────────────────────────────────────────────────

# 功能：验证 bash 工具默认策略是 ASK
# 设计：无任何 patterns 命中时，bash 必须询问用户，这是安全底线
def test_bash_default_is_ask() -> None:
    result = evaluate("bash", {"command": "echo hi"})
    assert result == PermissionDecision.ASK


# 功能：验证 read_file / list_dir / note_save 默认策略是 ALLOW
# 设计：只读或安全工具默认不打扰用户，降低权限疲劳
def test_safe_tools_default_allow() -> None:
    assert evaluate("read_file", {"path": "README.md"}) == PermissionDecision.ALLOW
    assert evaluate("list_dir", {"path": "."}) == PermissionDecision.ALLOW
    assert evaluate("note_save", {"content": "x"}) == PermissionDecision.ALLOW


# 功能：验证 write_file 默认策略是 ASK
# 设计：写文件有副作用，默认需要确认
def test_write_file_default_is_ask() -> None:
    assert evaluate("write_file", {"path": "out.txt", "content": "hi"}) == PermissionDecision.ASK


# 功能：验证未知工具默认策略是 ASK
# 设计：未在 DEFAULT_POLICIES 中登记的工具应采用最保守策略，防止漏配工具直接执行
def test_unknown_tool_default_is_ask() -> None:
    assert evaluate("some_future_tool", {}) == PermissionDecision.ASK


# ── non-bash tools ─────────────────────────────────────────────────────────────

# 功能：验证非 bash 工具的 patterns 不参与评估（patterns 仅对 bash 生效）
# 设计：write_file 有 deny_patterns 字段但工具不是 bash，应走 default (ASK)
def test_patterns_only_apply_to_bash() -> None:
    policy = ToolPolicy(
        default=PermissionDecision.ASK,
        deny_patterns=[r".*"],  # would deny everything if applied
        allow_patterns=[r".*"],
    )
    # write_file is not bash — patterns should be ignored → falls to default
    result = evaluate("write_file", {"path": "x.txt", "content": "hi"}, policy)
    assert result == PermissionDecision.ASK


# ── param_preview ─────────────────────────────────────────────────────────────

# 功能：验证 param_preview 对已知工具返回 key='value' 格式的摘要
# 设计：TUI 审批卡片依赖这个摘要让用户快速理解工具要做什么，格式必须稳定
def test_param_preview_known_tools() -> None:
    assert param_preview("bash", {"command": "echo hi"}) == "command='echo hi'"
    assert param_preview("read_file", {"path": "README.md"}) == "path='README.md'"
    assert param_preview("note_save", {"content": "Python 3.12"}) == "content='Python 3.12'"


# 功能：验证 param_preview 超出 60 字符时截断并加省略号
# 设计：避免审批卡片展示超长命令撑破 UI 布局
def test_param_preview_truncates_long_value() -> None:
    long_cmd = "echo " + "x" * 100
    preview = param_preview("bash", {"command": long_cmd})
    assert len(preview) <= 75  # key='<60 chars>…' overhead ~11 chars
    assert "…" in preview
