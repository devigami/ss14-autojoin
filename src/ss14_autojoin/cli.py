"""Command line: ``ss14-autojoin status|watch|join <address>`` and ``ss14-autojoin doctor``.

Joining (``join``) arrives with milestone M2; see ``docs/plan.md``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .joiner import Joiner, JoinerConfig
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

    join = commands.add_parser("join", help="watch the server and connect through the launcher when a slot is free")
    _add_address(join)
    join.add_argument("--launcher", type=Path, default=None, help="launcher install folder (auto-detected otherwise)")
    join.add_argument("--interval", type=float, default=3.0, help="seconds between polls (default 3, minimum 1)")
    join.add_argument("--margin", type=int, default=0, help="require this many free slots beyond one (default 0)")
    join.add_argument(
        "--attempt-timeout",
        type=float,
        default=60.0,
        help="seconds after the client starts until the attempt must be decided (default 60)",
    )
    join.add_argument(
        "--on-unknown",
        choices=("keep", "retry"),
        default="keep",
        help="when nothing shows success or failure by the timeout: keep the client and stop (default), "
        "or close it and retry",
    )
    join.add_argument("--cooldown", type=float, default=2.0, help="seconds to wait after a failed attempt")
    join.add_argument("--max-attempts", type=int, default=None, help="stop after this many attempts")
    join.add_argument(
        "--rejoin", action="store_true", help="after a join, start over when the client exits or is disconnected"
    )
    join.add_argument(
        "--restart-launcher", action="store_true", help="restart the launcher when it drops connect commands"
    )
    join.add_argument("--skip-panic-bunker", action="store_true", help="do not attempt while the panic bunker is on")
    join.add_argument(
        "--verbose", "-v", action="store_true", help="log what the tool does with the launcher and client"
    )
    join.add_argument("--quiet", "-q", action="store_true", help="no sound when the join lands or the loop stops")

    probe = commands.add_parser(
        "probe", help="show what the tool can see of a running game client (checks the UDP-socket signal)"
    )
    probe.add_argument("--pid", type=int, default=None, help="client PID (default: the newest SS14.Loader process)")
    probe.add_argument("--seconds", type=float, default=10.0, help="how long to sample (default 10)")

    commands.add_parser("gui", help="open the window with the settings panel and Start/Stop")
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
    from .notify import fanfare_path  # noqa: PLC0415

    print(f"join sound:        {fanfare_path() or 'missing (falls back to the alert sound)'}")
    return EXIT_OK


def cmd_join(args: argparse.Namespace) -> int:
    from .runtime import RealPorts  # noqa: PLC0415 - imports psutil lazily

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s"
    )
    address = ServerAddress.parse(args.address)
    data_dir = launcher_data_dir()
    install = find_launcher(args.launcher, launcher_log_dir=data_dir / "logs", process_exes=running_launcher_exes)
    if install is None:
        print("error: launcher installation not found; pass --launcher <folder that holds bin_x64>", file=sys.stderr)
        return EXIT_UNREACHABLE
    print(f"launcher: {install.launcher_exe} ({install.flavour}, via {install.source})")
    print(f"logs:     {data_dir / 'logs'}")
    config = JoinerConfig(
        address=address,
        interval=args.interval,
        margin=args.margin,
        attempt_timeout=args.attempt_timeout,
        unknown_policy=args.on_unknown,
        cooldown=args.cooldown,
        max_attempts=args.max_attempts,
        rejoin=args.rejoin,
        restart_launcher=args.restart_launcher,
        skip_panic_bunker=args.skip_panic_bunker,
    )
    joiner = Joiner(config, RealPorts(install, data_dir, status_timeout=args.timeout), listener=_print_event)
    print(f"watching {address.uri} via {address.status_url} (Ctrl+C to stop)", flush=True)
    try:
        outcome = joiner.run()
    except KeyboardInterrupt:
        print()
        return EXIT_INTERRUPTED
    if not args.quiet:
        from .notify import beep, play_success  # noqa: PLC0415

        if outcome.success:
            play_success()
            time.sleep(1.5)  # let the asynchronous playback finish before the process exits
        else:
            beep(1)
    return EXIT_OK if outcome.success else EXIT_UNREACHABLE


def cmd_probe(args: argparse.Namespace) -> int:
    import psutil  # noqa: PLC0415

    from .launcher import LOADER_EXE  # noqa: PLC0415
    from .runtime import udp_socket_count  # noqa: PLC0415

    pid = args.pid
    if pid is None:
        clients = [
            p
            for p in psutil.process_iter(["name", "create_time"])
            if (p.info.get("name") or "").lower() == LOADER_EXE.lower()
        ]
        if not clients:
            print("no running game client (SS14.Loader) found; pass --pid", file=sys.stderr)
            return EXIT_UNREACHABLE
        pid = max(clients, key=lambda p: p.info.get("create_time") or 0).pid
    print(f"client pid {pid}: sampling UDP sockets for {args.seconds:g} s (a connected client keeps one open)")
    deadline = time.monotonic() + args.seconds
    while True:
        count = udp_socket_count(pid)
        alive = psutil.pid_exists(pid)
        print(f"[{time.strftime('%H:%M:%S')}] alive={alive} udp_sockets={count}", flush=True)
        if time.monotonic() >= deadline or not alive:
            break
        time.sleep(1.0)
    return EXIT_OK


def _print_event(kind: str, message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {kind:8s} {message}", flush=True)


def cmd_gui(args: argparse.Namespace) -> int:
    from .app import main as gui_main  # noqa: PLC0415 - tkinter only when asked for

    return gui_main()


_COMMANDS = {
    "status": cmd_status,
    "watch": cmd_watch,
    "doctor": cmd_doctor,
    "join": cmd_join,
    "probe": cmd_probe,
    "gui": cmd_gui,
}


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
