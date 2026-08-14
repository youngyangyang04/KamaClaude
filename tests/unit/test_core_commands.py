from __future__ import annotations

import os
from pathlib import Path

from pytest import MonkeyPatch

from scott_claude.cli.commands import core


# 功能：验证跨平台 PID 检测能识别当前测试进程
# 设计：使用当前进程避免创建额外子进程，同时覆盖 Windows OpenProcess 与 POSIX 信号探测分支
def test_pid_exists_for_current_process() -> None:
    assert core._pid_exists(os.getpid())


# 功能：验证 PID 文件指向存活进程时返回对应 PID
# 设计：替换进程探测函数以隔离操作系统差异，聚焦 PID 文件解析和存活分支
def test_running_pid_returns_live_process(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    pid_file = tmp_path / "scott-core.pid"
    pid_file.write_text("1234")
    monkeypatch.setattr(core, "_PID_FILE", pid_file)
    monkeypatch.setattr(core, "_pid_exists", lambda pid: pid == 1234)

    assert core._running_pid() == 1234
    assert pid_file.exists()


# 功能：验证 PID 文件指向已退出进程时会删除陈旧文件
# 设计：让进程探测稳定返回假，断言返回值和清理副作用，避免依赖可复用的真实 PID
def test_running_pid_removes_stale_file(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    pid_file = tmp_path / "scott-core.pid"
    pid_file.write_text("1234")
    monkeypatch.setattr(core, "_PID_FILE", pid_file)
    monkeypatch.setattr(core, "_pid_exists", lambda _pid: False)

    assert core._running_pid() is None
    assert not pid_file.exists()
