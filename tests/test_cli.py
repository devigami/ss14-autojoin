from __future__ import annotations

import argparse
import json

import pytest

from ss14_autojoin.cli import EXIT_OK, EXIT_UNREACHABLE, EXIT_USAGE, format_status, main
from ss14_autojoin.server import ServerStatus
from tests.conftest import STATUS_FULL, FakeStatusServer


def test_status_summary(fake_server: FakeStatusServer, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["status", fake_server.address]) == EXIT_OK
    out = capsys.readouterr().out
    assert f"http://127.0.0.1:{fake_server.port}/status" in out
    assert "Wizard's Den Lizard [NA West] | 80/80 players | full | run level in round | map Box | round 12345" in out


def test_status_json(fake_server: FakeStatusServer, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["status", fake_server.address, "--json"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out) == STATUS_FULL


def test_status_invalid_address(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["status", "http://nope"]) == EXIT_USAGE
    assert "error:" in capsys.readouterr().err


def test_status_unreachable(fake_server: FakeStatusServer, capsys: pytest.CaptureFixture[str]) -> None:
    fake_server.code = 500
    assert main(["status", fake_server.address]) == EXIT_UNREACHABLE
    assert "error:" in capsys.readouterr().err


def test_watch_prints_only_changes(fake_server: FakeStatusServer, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["watch", fake_server.address, "--interval", "0", "--max-polls", "3"]) == EXIT_OK
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith(
        f"watching ss14://127.0.0.1:{fake_server.port} via http://127.0.0.1:{fake_server.port}/status"
    )
    assert len(lines) == 2, lines
    assert lines[1].endswith("| full | run level in round | map Box | round 12345")
    assert len(fake_server.requests) == 3


def test_watch_reports_slot_and_offline(fake_server: FakeStatusServer, capsys: pytest.CaptureFixture[str]) -> None:
    fake_server.set_status({**STATUS_FULL, "players": 79})
    assert main(["watch", fake_server.address, "--interval", "0", "--max-polls", "1"]) == EXIT_OK
    assert "| slot free |" in capsys.readouterr().out
    assert main(["watch", fake_server.address, "--interval", "0", "--max-polls", "1", "--margin", "1"]) == EXIT_OK
    assert "| full |" in capsys.readouterr().out
    fake_server.code = 404
    assert main(["watch", fake_server.address, "--interval", "0", "--max-polls", "1"]) == EXIT_OK
    assert "offline:" in capsys.readouterr().out


def test_format_status_without_cap_or_round() -> None:
    line = format_status(ServerStatus.from_json({"name": "bare", "players": 3, "panic_bunker": True}))
    assert line == "bare | 3/no cap players | slot free | run level unknown | panic bunker on"


def test_doctor_reports_install(tmp_path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    from ss14_autojoin import launcher as L

    root = tmp_path / "Inst"
    (root / "bin_x64" / "loader").mkdir(parents=True)
    (root / "bin_x64" / L.LAUNCHER_EXE).write_bytes(b"")
    monkeypatch.setattr("ss14_autojoin.cli.running_launcher_exes", list)
    assert main(["doctor", "--launcher", str(root)]) == EXIT_OK
    out = capsys.readouterr().out
    assert f"launcher install:  {root} (standalone, found via configured)" in out
    assert "loader exe:        missing" in out
    assert main(["doctor", "--launcher", str(tmp_path / "nothing")]) == EXIT_UNREACHABLE


def test_join_without_launcher_fails_cleanly(
    tmp_path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ss14_autojoin.cli.running_launcher_exes", list)
    monkeypatch.setattr("ss14_autojoin.cli.find_launcher", lambda *a, **k: None)
    assert main(["join", "ss14://host", "--launcher", str(tmp_path)]) == EXIT_UNREACHABLE
    assert "launcher installation not found" in capsys.readouterr().err


def test_launcher_command_sets_dotnet_root(tmp_path) -> None:
    from ss14_autojoin.launcher import LauncherInstall
    from ss14_autojoin.runtime import launcher_command

    install = LauncherInstall(tmp_path, tmp_path / "bin_x64" / "x.exe", None, tmp_path / "dotnet_x64", "t", "steam")
    argv, env = launcher_command(install, "ss14s://lizard.spacestation14.io/server")
    assert argv == [str(tmp_path / "bin_x64" / "x.exe"), "ss14s://lizard.spacestation14.io/server"]
    assert env["DOTNET_ROOT"] == str(tmp_path / "dotnet_x64")


def test_parser_knows_every_command_and_join_flags() -> None:
    from ss14_autojoin.cli import _COMMANDS, build_parser

    parser = build_parser()
    subparsers = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    assert set(subparsers.choices) == set(_COMMANDS) == {"status", "watch", "doctor", "join", "probe", "gui"}
    args = parser.parse_args(["join", "ss14://host", "--on-unknown", "retry", "--attempt-timeout", "30"])
    assert args.on_unknown == "retry" and args.attempt_timeout == 30.0
    assert parser.parse_args(["join", "ss14://host"]).on_unknown == "keep"
    assert parser.parse_args(["probe", "--seconds", "5"]).seconds == 5.0
