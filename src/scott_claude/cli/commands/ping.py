from __future__ import annotations

import asyncio
import json
import sys
import time

import scott_claude
from scott_claude.core.bus.commands import PongResult
from scott_claude.core.bus.envelope import JsonRpcError, JsonRpcSuccess
from scott_claude.core.config import ScottConfig


# 同步入口：运行 ping 协程，连接失败时打印错误并退出
def cmd_ping(config: ScottConfig) -> None:
    try:
        # 同步代码启动异步代码时，通常使用： asyncio.run(...)
        # 调用 async 函数 _ping() → 得到协程对象 _ping(config)
        # 协程对象_ping(config)交给事件循环 asyncio.run(...)  → 才真正执行
        asyncio.run(_ping(config))
    except (ConnectionRefusedError, OSError):
        print(f"error: core not running ({config.host}:{config.port})", file=sys.stderr)
        sys.exit(1)


# 向 core 守护进程发送 ping 请求，打印 pong 响应及延迟
async def _ping(config: ScottConfig) -> None:
    t0 = time.monotonic()
    reader, writer = await asyncio.open_connection(config.host, config.port)

    req = {
        "jsonrpc": "2.0",
        "id": "cli-1",
        # method: 表示要求 daemon 执行的方法
        "method": "core.ping",
        "params": {"client": f"cli/{scott_claude.__version__}"},
    }
    # 数据进入发送缓冲区
    writer.write((json.dumps(req) + "\n").encode())
    # drain() 的作用可以理解为：如果发送缓冲区堆积太多，就等待缓冲区有空间，确保数据能够继续发送。在少量数据时，它通常很快返回。
    # 确保数据正常交给底层网络系统
    await writer.drain()

    line = await asyncio.wait_for(reader.readline(), timeout=10.0)
    latency_ms = int((time.monotonic() - t0) * 1000)

    writer.close()
    await writer.wait_closed()

    raw = json.loads(line)
    if "error" in raw:
        err = JsonRpcError.model_validate(raw)
        print(f"error: {err.error.code} {err.error.message}", file=sys.stderr)
        sys.exit(1)

    resp = JsonRpcSuccess.model_validate(raw)
    result = PongResult.model_validate(resp.result)
    print(f"pong server={result.server_version} uptime={result.uptime_ms}ms latency={latency_ms}ms")
