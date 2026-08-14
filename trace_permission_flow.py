#!/usr/bin/env python3
"""
端到端权限审批流程诊断脚本

模拟 TUI 的完整链路：
  1. 连接 scott-core，订阅事件
  2. 创建 session，发消息触发 bash 工具（bash 总是需要审批）
  3. 收到 permission.requested → 自动回复 allow_once
  4. 等待 run.finished，打印全部事件日志

运行：uv run python trace_permission_flow.py
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

HOST = "127.0.0.1"
PORT = 7437
GOAL = "用 bash 执行 `echo hello_permission_test`，把结果告诉我"


async def send(writer: asyncio.StreamWriter, method: str, params: dict[str, Any]) -> str:
    req_id = str(uuid.uuid4())
    msg = json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})
    writer.write(msg.encode() + b"\n")
    await writer.drain()
    return req_id


async def main() -> None:
    print(f"[connect] {HOST}:{PORT}")
    reader, writer = await asyncio.open_connection(HOST, PORT, limit=2 * 1024 * 1024)

    pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
    loop = asyncio.get_running_loop()
    events_log: list[dict[str, Any]] = []
    permission_event: dict[str, Any] | None = None
    finished = asyncio.Event()

    # ── 读循环 ────────────────────────────────────────────────────────
    async def read_loop() -> None:
        nonlocal permission_event
        while True:
            line = await reader.readline()
            if not line:
                print("[read_loop] connection closed")
                finished.set()
                return
            msg: dict[str, Any] = json.loads(line)

            # RPC 响应
            if "jsonrpc" in msg:
                req_id = msg.get("id")
                if req_id and req_id in pending:
                    fut = pending.pop(req_id)
                    if not fut.done():
                        if "error" in msg:
                            fut.set_exception(RuntimeError(str(msg["error"])))
                        else:
                            fut.set_result(msg.get("result") or {})
                continue

            # 推送事件
            if msg.get("kind") == "event":
                event = msg.get("event", {})
                t = event.get("type", "?")
                events_log.append(event)
                print(f"  [event] {t:35s}  {_brief(event)}")

                if t == "permission.requested":
                    permission_event = event
                    tool_use_id = event["tool_use_id"]
                    print(f"\n  *** 收到 permission.requested  tool={event['tool_name']}")
                    print(f"      param_preview={event.get('param_preview')!r}")
                    print(f"      → 自动回复 allow_once\n")
                    # 直接在读循环里发 permission.respond
                    req_id2 = await send(writer, "permission.respond",
                                         {"tool_use_id": tool_use_id, "decision": "allow_once"})
                    fut2: asyncio.Future[dict[str, Any]] = loop.create_future()
                    pending[req_id2] = fut2

                if t == "run.finished":
                    finished.set()

    read_task = asyncio.create_task(read_loop())

    # ── subscribe ─────────────────────────────────────────────────────
    sub_id = await send(writer, "event.subscribe", {
        "topics": ["session.*", "run.*", "step.*", "tool.*",
                   "llm.token", "llm.usage", "log.*", "permission.*"],
        "scope": "global",
    })
    sub_fut: asyncio.Future[dict[str, Any]] = loop.create_future()
    pending[sub_id] = sub_fut
    sub_result = await sub_fut
    print(f"[subscribed] subscription_id={sub_result.get('subscription_id')}")

    # ── session.create ────────────────────────────────────────────────
    sess_id = await send(writer, "session.create", {"mode": "chat"})
    sess_fut: asyncio.Future[dict[str, Any]] = loop.create_future()
    pending[sess_id] = sess_fut
    sess_result = await sess_fut
    session_id = sess_result["session_id"]
    print(f"[session]   session_id={session_id}")

    # ── session.send_message ──────────────────────────────────────────
    print(f"\n[send]      goal={GOAL!r}\n")
    msg_id = await send(writer, "session.send_message",
                        {"session_id": session_id, "content": GOAL})
    msg_fut: asyncio.Future[dict[str, Any]] = loop.create_future()
    pending[msg_id] = msg_fut

    # ── 等最多 60 秒 ──────────────────────────────────────────────────
    try:
        await asyncio.wait_for(finished.wait(), timeout=60)
    except TimeoutError:
        print("\n[TIMEOUT] 60 秒内未收到 run.finished")

    read_task.cancel()
    writer.close()

    print("\n── 汇总 ──")
    types = [e.get("type") for e in events_log]
    for t in dict.fromkeys(types):   # preserve order, deduplicate
        cnt = types.count(t)
        print(f"  {t:40s} × {cnt}")

    if permission_event is None:
        print("\n[WARN] 未收到 permission.requested 事件！")
    else:
        print("\n[OK] 完整流程走通，permission.requested 已收到并回复。")


def _brief(e: dict[str, Any]) -> str:
    skip = {"type", "ts", "run_id", "session_id"}
    parts = [f"{k}={v!r}" for k, v in e.items() if k not in skip]
    s = "  ".join(parts)
    return s[:120] + "…" if len(s) > 120 else s


if __name__ == "__main__":
    asyncio.run(main())
