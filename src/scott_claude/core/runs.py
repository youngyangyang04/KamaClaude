from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

RUNS_DIR = Path("runs")


# 返回指定 run_id 对应的目录路径
def run_dir(run_id: str) -> Path:
    return RUNS_DIR / run_id


# 返回指定 run_id 的事件日志文件路径
def events_file(run_id: str) -> Path:
    return run_dir(run_id) / "events.jsonl"


# 生成格式为 YYYYMMDD-HHMMSS-xxxxxx 的唯一 run ID
def new_run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"{ts}-{suffix}"


# 创建 run 目录（含父级）并返回路径
def ensure_run_dir(run_id: str) -> Path:
    path = run_dir(run_id)
    path.mkdir(parents=True, exist_ok=True)
    return path
