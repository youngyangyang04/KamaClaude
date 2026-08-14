from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from scott_claude.core.config import ScottConfig

_TEXT_FMT = 'level=%(levelname)s ts=%(asctime)s source=%(name)s msg="%(message)s"'
_JSON_FMT = '{"level":"%(levelname)s","ts":"%(asctime)s","source":"%(name)s","msg":"%(message)s"}'


# 根据配置初始化 root logger：设置级别、格式，并挂载 stderr 和可选的滚动文件 handler
def setup_logging(config: ScottConfig) -> None:
    level = getattr(logging, config.logging.level.upper(), logging.INFO)
    fmt = _JSON_FMT if config.logging.format == "json" else _TEXT_FMT
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S")

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    root.addHandler(stderr_handler)

    if config.logging.file:
        log_path = Path(config.logging.file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
