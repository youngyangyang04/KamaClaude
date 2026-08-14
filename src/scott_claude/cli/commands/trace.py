from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from scott_claude.core.config import ScottConfig
from scott_claude.core.trace.record import TraceRecord

_COLORS = {
    "CLIENT→CORE": "\033[36m",
    "CORE→CLIENT": "\033[33m",
    "CORE":             "\033[32m",
    "CORE→LLM":   "\033[35m",
    "LLM→CORE":   "\033[34m",
}
_RESET = "\033[0m"
_BOLD = "\033[1m"


# scott trace 子命令：从 daemon.jsonl 读取并展示 trace 记录
def cmd_trace(
    run_id: str | None,
    config: ScottConfig,
    *,
    layer: str | None = None,
    direction: str | None = None,
    raw: bool = False,
    follow: bool = False,
) -> None:
    trace_path = Path(config.trace.file).expanduser()
    if not trace_path.exists():
        print(f"trace file not found: {trace_path}", file=sys.stderr)
        sys.exit(1)

    with open(trace_path) as f:
        for line in f:
            _process_line(
                line.strip(),
                run_id=run_id,
                layer=layer,
                direction=direction,
                raw=raw,
            )

    if follow:
        with open(trace_path) as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    _process_line(
                        line.strip(),
                        run_id=run_id,
                        layer=layer,
                        direction=direction,
                        raw=raw,
                    )
                else:
                    time.sleep(0.05)


# 解析单行并根据过滤条件决定是否输出
def _process_line(
    line: str,
    *,
    run_id: str | None,
    layer: str | None,
    direction: str | None,
    raw: bool,
) -> None:
    if not line:
        return
    try:
        record = TraceRecord.model_validate(json.loads(line))
    except Exception:
        return

    if run_id is not None and record.run_id != run_id:
        return
    if layer is not None and record.layer != layer:
        return
    if direction is not None and record.direction != direction:
        return

    if raw:
        print(line)
    else:
        _print_record(record)


# 将单条 TraceRecord 格式化为彩色单行输出
def _print_record(record: TraceRecord) -> None:
    color = _COLORS.get(record.direction, "")
    ts = record.ts[11:23] if len(record.ts) >= 23 else record.ts

    direction_str = f"{color}{_BOLD}{record.direction:<14}{_RESET}"
    kind_str = f"{record.kind:<13}"

    parts: list[str] = []
    if record.run_id:
        parts.append(f"run={record.run_id[:8]}")
    if record.step is not None:
        parts.append(f"step={record.step}")
    parts.append(_summarize(record))

    print(f"{ts}  {direction_str}  {kind_str}  {'  '.join(parts)}")


# 从 data 字段提取关键摘要（不输出大型 payload）
def _summarize(record: TraceRecord) -> str:
    data = record.data
    kind = record.kind

    if kind == "command":
        params = data.get("params", {})
        goal = str(params.get("goal", ""))
        suffix = f'  goal="{goal[:50]}"' if goal else ""
        return f"method={data.get('method')}{suffix}"

    if kind == "response":
        result = data.get("result", {})
        if isinstance(result, dict) and "run_id" in result:
            return f"run_id={result['run_id'][:8]}"
        return str(result)[:60]

    if kind == "error":
        err = data.get("error", {})
        return f"code={err.get('code')}  {err.get('message', '')}"

    if kind == "push":
        return f"event={data.get('event_type')}  sub={data.get('sub_id')}"

    if kind == "event":
        return f"type={data.get('type')}"

    if kind == "api_call":
        msgs = data.get("messages")
        count = len(msgs) if isinstance(msgs, list) else data.get("message_count", "?")
        tools = data.get("tool_schemas")
        tc = len(tools) if isinstance(tools, list) else data.get("tool_count", "?")
        return f"msgs={count}  tools={tc}"

    if kind == "api_response":
        usage = data.get("usage", {})
        return (
            f"stop={data.get('stop_reason')}  "
            f"latency={data.get('latency_ms')}ms  "
            f"out_tokens={usage.get('output_tokens', '?')}"
        )

    return str(data)[:60]
