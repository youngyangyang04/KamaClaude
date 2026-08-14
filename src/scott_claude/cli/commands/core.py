from __future__ import annotations

import asyncio
import ctypes
import os
import signal
import subprocess
import sys
from pathlib import Path

from scott_claude.core.config import ScottConfig

_PID_FILE = Path.home() / ".scott" / "scott-core.pid"
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_ERROR_ACCESS_DENIED = 5


# 尝试连接 daemon，成功则正常返回，失败则抛出 ConnectionRefusedError/OSError
async def _ping_check(config: ScottConfig) -> None:
    _r, w = await asyncio.open_connection(config.host, config.port)
    w.close()
    await w.wait_closed()


# 跨平台检查指定 PID 是否仍对应一个存活进程
def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False

    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        open_process.restype = ctypes.c_void_p
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [ctypes.c_void_p]
        close_handle.restype = ctypes.c_int

        ctypes.set_last_error(0)
        handle = open_process(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            close_handle(handle)
            return True
        return ctypes.get_last_error() == _ERROR_ACCESS_DENIED

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# 读取 PID 文件并确认进程存活，进程已消失则删除文件并返回 None
def _running_pid() -> int | None:
    if not _PID_FILE.exists():
        return None
    try:
        pid = int(_PID_FILE.read_text().strip())
    except (OSError, ValueError):
        _PID_FILE.unlink(missing_ok=True)
        return None
    if not _pid_exists(pid):
        _PID_FILE.unlink(missing_ok=True)
        return None
    return pid


# 打印 daemon 当前状态（running / not running）
def cmd_core_status(config: ScottConfig) -> None:
    try:
        asyncio.run(_ping_check(config))
        print(f"running  ({config.host}:{config.port})")
    except (ConnectionRefusedError, OSError):
        print("not running")


# 在后台启动 daemon，若已在运行则提示并退出
def cmd_core_start(config: ScottConfig) -> None:
    try:
        asyncio.run(_ping_check(config))
        print(f"already running  ({config.host}:{config.port})")
        return
    except (ConnectionRefusedError, OSError):
        pass

    proc = subprocess.Popen(
        [sys.executable, "-m", "scott_claude.core"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(proc.pid))
    print(f"started  pid={proc.pid}  ({config.host}:{config.port})")


# 向 daemon 发送 SIGTERM 停止进程，若未运行则提示
def cmd_core_stop(config: ScottConfig) -> None:
    pid = _running_pid()
    if pid is None:
        print("not running")
        return
    os.kill(pid, signal.SIGTERM)
    _PID_FILE.unlink(missing_ok=True)
    print(f"stopped  pid={pid}")
