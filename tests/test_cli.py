from __future__ import annotations

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
