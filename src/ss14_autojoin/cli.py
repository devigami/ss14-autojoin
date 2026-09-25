"""Command line: ``ss14-autojoin status|watch <address>`` and ``ss14-autojoin doctor``.

Joining (``join``) arrives with milestone M2; see ``docs/plan.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .launcher import find_launcher, launcher_data_dir, running_launcher_exes
from .server import STATUS_TIMEOUT, AddressError, ServerAddress, ServerStatus, ServerUnreachable, fetch_status

EXIT_OK = 0
EXIT_UNREACHABLE = 1
EXIT_USAGE = 2
EXIT_INTERRUPTED = 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ss14-autojoin",
        description="Watch a Space Station 14 server and join it through the launcher when a slot is free.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    status = commands.add_parser("status", help="fetch the server's /status once and print it")
    _add_address(status)
    status.add_argument("--json", action="store_true", help="print the raw status JSON instead of a summary")

    watch = commands.add_parser("watch", help="poll /status and print whenever the slot situation changes")
    _add_address(watch)
    watch.add_argument("--interval", type=float, default=3.0, help="seconds between polls (default 3, minimum 1)")
    watch.add_argument("--margin", type=int, default=0, help="require this many free slots beyond one (default 0)")
    watch.add_argument(
        "--max-polls", type=int, default=None, help="stop after this many polls (default: run until Ctrl+C)"
    )

    doctor = commands.add_parser("doctor", help="find the launcher installation and data folders and print them")
    doctor.add_argument("--launcher", type=Path, default=None, help="launcher install folder to check first")
    return parser


def _add_address(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "address", help="ss14://host[:port] or ss14s://host; the scheme is optional, the port defaults to 1212"
    )
    parser.add_argument(
        "--timeout", type=float, default=STATUS_TIMEOUT, help="status request timeout in seconds (default 5)"
    )


def format_status(status: ServerStatus, margin: int = 0) -> str:
    """One line: name, players/cap, the slot decision for ``margin``, round state."""
    cap = str(status.soft_max_players) if status.soft_max_players else "no cap"
    level = status.run_level.name.lower().replace("_", " ") if status.run_level is not None else "unknown"
    parts = [
        status.name or "?",
        f"{status.players}/{cap} players",
        "slot free" if status.has_free_slot(margin) else "full",
        f"run level {level}",
    ]
    if status.map:
        parts.append(f"map {status.map}")
    if status.round_id is not None:
        parts.append(f"round {status.round_id}")
    if status.panic_bunker:
        parts.append("panic bunker on")
    return " | ".join(parts)


def cmd_status(args: argparse.Namespace) -> int:
    address = ServerAddress.parse(args.address)
    status = fetch_status(address, timeout=args.timeout)
    if args.json:
        print(json.dumps(status.raw, indent=2))
    else:
        print(address.status_url)
        print(format_status(status))
    return EXIT_OK


def cmd_watch(args: argparse.Namespace) -> int:
    address = ServerAddress.parse(args.address)
    interval = max(1.0, args.interval) if args.max_polls is None else max(0.0, args.interval)
    print(f"watching {address.uri} via {address.status_url} every {interval:g} s (Ctrl+C to stop)", flush=True)
    last_key: tuple[str, int | None] | None = None
    polls = 0
    while args.max_polls is None or polls < args.max_polls:
        polls += 1
        try:
            status = fetch_status(address, timeout=args.timeout)
        except ServerUnreachable as e:
            key: tuple[str, int | None] = ("offline", None)
            line = f"offline: {e.cause}"
        else:
            key = ("free" if status.has_free_slot(args.margin) else "full", status.players)
            line = format_status(status, args.margin)
        if key != last_key:
            print(f"[{time.strftime('%H:%M:%S')}] {line}", flush=True)
            last_key = key
        if args.max_polls is not None and polls >= args.max_polls:
            break
        time.sleep(interval)
    return EXIT_OK


def cmd_doctor(args: argparse.Namespace) -> int:
    data_dir = launcher_data_dir()
    print(f"launcher data dir: {data_dir} ({'exists' if data_dir.is_dir() else 'missing'})")
    print(f"launcher log dir:  {data_dir / 'logs'}")
    print(f"client stdout log: {data_dir / 'logs' / 'client.stdout.log'}")
    install = find_launcher(args.launcher, launcher_log_dir=data_dir / "logs", process_exes=running_launcher_exes)
    if install is None:
        print("launcher install:  not found (pass --launcher <folder that holds bin_x64>)")
        return EXIT_UNREACHABLE
    print(f"launcher install:  {install.root} ({install.flavour}, found via {install.source})")
    print(f"launcher exe:      {install.launcher_exe}")
    print(f"loader exe:        {install.loader_exe or 'missing'}")
    print(f"dotnet root:       {install.dotnet_root or 'missing (a system-wide .NET runtime is then required)'}")
    return EXIT_OK


_COMMANDS = {"status": cmd_status, "watch": cmd_watch, "doctor": cmd_doctor}


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _COMMANDS[args.command](args)
    except AddressError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_USAGE
    except ServerUnreachable as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_UNREACHABLE
    except KeyboardInterrupt:
        print()
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    raise SystemExit(main())
