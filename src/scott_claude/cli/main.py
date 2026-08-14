from __future__ import annotations

import argparse
import sys

from scott_claude.cli.commands.chat import cmd_chat
from scott_claude.cli.commands.core import cmd_core_start, cmd_core_status, cmd_core_stop
from scott_claude.cli.commands.ping import cmd_ping
from scott_claude.cli.commands.preset import (
    cmd_preset_export,
    cmd_preset_import,
    cmd_preset_list,
    cmd_preset_new,
    cmd_preset_show,
    cmd_preset_validate,
)
from scott_claude.cli.commands.run import cmd_run
from scott_claude.cli.commands.trace import cmd_trace
from scott_claude.cli.commands.version import cmd_version
from scott_claude.core.config import get_config
from scott_claude.core.logging_setup import setup_logging


# CLI 主入口：解析命令行参数并分发到对应子命令
def main() -> None:
    # 创建一个主命令解析器 parser, prog="scott" 表示程序名称叫 scott, 输入 scott --help,
    # usage: scott [-h] [--version] {ping} ...
    # ScottClaude CLI
    parser = argparse.ArgumentParser(prog="scott", description="ScottClaude CLI")
    # 添加 --version 参数 , action="store_true"表示, 如果用户输入 --version, 则触发该参数(args.version == True)
    parser.add_argument("--version", action="store_true", help="Print version and exit")

    # 创建子命令解析器 subparsers, dest="command" 表示将子命令名称保存在 args.command 中, subparsers和--version同级
    subparsers = parser.add_subparsers(dest="command")

    # 注册/添加 ping 子命令
    subparsers.add_parser("ping", help="Ping the core daemon")
    # 添加 chat 子命令
    subparsers.add_parser("chat", help="Start a multi-turn chat session")

    # 添加 run 子命令
    run_parser = subparsers.add_parser("run", help="Run an agent task")
    run_parser.add_argument("--goal", required=True, help="Goal for the agent to accomplish")

    core_parser = subparsers.add_parser("core", help="Manage the core daemon")
    core_sub = core_parser.add_subparsers(dest="core_command")
    core_sub.add_parser("start", help="Start the daemon in the background")
    core_sub.add_parser("stop", help="Stop the running daemon")
    core_sub.add_parser("status", help="Show daemon status")

    trace_parser = subparsers.add_parser("trace", help="View system trace log")
    trace_parser.add_argument("run_id", nargs="?", default=None, help="Filter by run ID")
    trace_parser.add_argument("--layer", choices=["ipc", "event", "llm"], help="Filter by layer")
    trace_parser.add_argument("--direction", help="Filter by direction (e.g. CORE→LLM)")
    trace_parser.add_argument("--raw", action="store_true", help="Output raw NDJSON")
    trace_parser.add_argument("--follow", "-f", action="store_true", help="Follow new records")

    preset_parser = subparsers.add_parser("preset", help="Manage agent presets and skills")
    preset_sub = preset_parser.add_subparsers(dest="preset_command")
    preset_list_p = preset_sub.add_parser("list", help="List presets (B/G/L tiers)")
    preset_list_p.add_argument("--kind", choices=["agent", "skill", "all"], default="all")
    preset_show_p = preset_sub.add_parser("show", help="Show a preset in detail")
    preset_show_p.add_argument("kind", choices=["agent", "skill"])
    preset_show_p.add_argument("name")
    preset_validate_p = preset_sub.add_parser("validate", help="Validate a preset file")
    preset_validate_p.add_argument("kind", choices=["agent", "skill"])
    preset_validate_p.add_argument("file")
    preset_new_p = preset_sub.add_parser("new", help="Create a preset from a template")
    preset_new_p.add_argument("name")
    preset_new_p.add_argument("--kind", choices=["agent", "skill"], required=True)
    preset_export_p = preset_sub.add_parser("export", help="Export a preset as Markdown package")
    preset_export_p.add_argument("kind", choices=["agent", "skill"])
    preset_export_p.add_argument("name")
    preset_export_p.add_argument(
        "-o", "--out", default=None,
        help="Output path (default ./workspace/<name>.<kind>.md)",
    )
    preset_import_p = preset_sub.add_parser("import", help="Import a Markdown preset package")
    preset_import_p.add_argument("file")
    preset_import_p.add_argument(
        "--global", dest="global_", action="store_true",
        help="Write to ~/.scott instead of .scott/",
    )

    args = parser.parse_args()

    if args.version:
        cmd_version()
        return

    config = get_config()
    setup_logging(config)

    if args.command == "ping":
        cmd_ping(config)
    elif args.command == "chat":
        cmd_chat(config)
    elif args.command == "run":
        cmd_run(args.goal, config)
    elif args.command == "core":
        if args.core_command == "start":
            cmd_core_start(config)
        elif args.core_command == "stop":
            cmd_core_stop(config)
        elif args.core_command == "status":
            cmd_core_status(config)
        else:
            core_parser.print_help()
            sys.exit(1)
    elif args.command == "trace":
        cmd_trace(
            args.run_id,
            config,
            layer=args.layer,
            direction=args.direction,
            raw=args.raw,
            follow=args.follow,
        )
    elif args.command == "preset":
        if args.preset_command == "list":
            cmd_preset_list(args.kind, config)
        elif args.preset_command == "show":
            cmd_preset_show(args.kind, args.name, config)
        elif args.preset_command == "validate":
            cmd_preset_validate(args.kind, args.file, config)
        elif args.preset_command == "new":
            cmd_preset_new(args.name, args.kind, config)
        elif args.preset_command == "export":
            cmd_preset_export(args.kind, args.name, args.out, config)
        elif args.preset_command == "import":
            cmd_preset_import(args.file, args.global_, config)
        else:
            preset_parser.print_help()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)
