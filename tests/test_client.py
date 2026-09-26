from __future__ import annotations

from pathlib import Path

from ss14_autojoin.client import (
    ClientLogState,
    DenyReason,
    LauncherLogTail,
    LogTail,
    parse_client_log,
    parse_launcher_line,
    parse_launcher_log,
)

FIXTURES = Path(__file__).resolve().parent.parent / "docs" / "development" / "fixtures"


def test_joined_fixture() -> None:
    state = parse_client_log((FIXTURES / "client.stdout.joined.log").read_text())
    assert state.outcome == "joined"
    assert state.host == "lizard.spacestation14.com" and state.port == 1212
    assert state.winning_endpoint == "51.81.194.242:1212"
    assert state.deny is None
    assert state.runlevel == "InGame"
    assert not state.exited
    assert state.summary == "joined"


def test_full_after_exit_fixture() -> None:
    state = parse_client_log((FIXTURES / "client.stdout.full-after-exit.log").read_text())
    assert state.outcome == "failed"
    assert state.deny is not None
    assert state.deny.text == "The server is full!"
    assert state.deny.delay == 30 and state.deny.redial is False
    assert state.deny.is_full and state.deny.retryable
    assert state.exited
    assert state.summary == "failed: The server is full!"


def test_truncated_fixture_is_pending() -> None:
    state = parse_client_log((FIXTURES / "client.stdout.full.log").read_text())
    assert state.outcome == "pending"
    assert state.summary == "starting"
    assert not state.connecting_or_later


def test_losing_candidate_disconnect_is_not_a_failure() -> None:
    state = ClientLogState()
    state.feed_lines(
        """[DEBG] net: Attempting to connect to host port 1212
[DEBG] net: "[::1]:1212": Status changed to InitiatedConnect, reason: "user called connect"
[DEBG] net: "1.2.3.4:1212": Status changed to InitiatedConnect, reason: "user called connect"
[DEBG] net: "1.2.3.4:1212": Status changed to Connected, reason: "Connected to ABC"
[DEBG] net: "[::1]:1212": Status changed to Disconnected, reason: "Connection attempt failed"
"""
    )
    assert state.outcome == "pending" and state.summary == "connecting"
    state.feed("[DEBG] net: Handshake completed, connection established.")
    assert state.outcome == "joined"
    state.feed('[INFO] net: "1.2.3.4:1212": Disconnected (Kicked)')  # not a status line; ignored
    kicked = '{\\"reason\\":\\"Kicked\\"}'
    state.feed(f'[DEBG] net: "1.2.3.4:1212": Status changed to Disconnected, reason: "Disconnected: {kicked}"')
    assert state.outcome == "joined"
    assert state.disconnected_after_join is not None and state.disconnected_after_join.text == "Kicked"
    assert "later disconnected: Kicked" in state.summary


def test_all_candidates_failed_is_a_failure() -> None:
    state = ClientLogState()
    state.feed_lines(
        """[DEBG] net: Attempting to connect to host port 1212
[DEBG] net: "1.2.3.4:1212": Status changed to InitiatedConnect, reason: "user called connect"
[DEBG] net: "1.2.3.4:1212": Status changed to Disconnected, reason: "Connection attempt failed"
"""
    )
    assert state.outcome == "failed"
    assert state.deny is not None and state.deny.text == "Connection attempt failed"
    assert not state.deny.retryable


def test_runlevel_initialize_after_connecting_fails_without_reason() -> None:
    state = ClientLogState()
    state.feed("[DEBG] client: Runlevel changed to: Initialize")  # start-up, before connecting
    assert state.outcome == "pending"
    state.feed("[DEBG] client: Runlevel changed to: Connecting")
    state.feed("[DEBG] net: Attempting to connect to host port 1212")
    state.feed("[DEBG] client: Runlevel changed to: Initialize")
    assert state.outcome == "failed" and state.deny is None
    assert state.summary == "failed: no reason logged"
    state.feed(
        "[ERRO] net: Exception during handshake: X: Disconnected: "
        '{"reason":"Connect denied: You are banned.","redial":false}'
    )
    assert state.deny is not None and state.deny.text == "You are banned." and not state.deny.retryable


def test_deny_reason_parsing() -> None:
    escaped = DenyReason.parse(
        '{\\"reason\\":\\"Connect denied: The server is full!\\",\\"redial\\":false,\\"delay\\":30}'
    )
    assert escaped.text == "The server is full!" and escaped.delay == 30.0 and escaped.is_full
    plain = DenyReason.parse("Disconnected: Timed out")
    assert plain.text == "Timed out" and plain.delay is None and not plain.retryable
    redial = DenyReason.parse('Disconnected: {"reason":"Version mismatch","redial":true}')
    assert redial.redial and not redial.retryable
    assert DenyReason.parse("{not json").text == "{not json"


def test_launcher_log_fixture_events() -> None:
    events = parse_launcher_log((FIXTURES / "launcher.log").read_text())
    kinds = [e.kind for e in events]
    assert kinds.count("client_started") == 4
    assert kinds.count("client_exited") == 6  # stdout and stderr each, for three exited clients
    assert kinds.count("connect_command") == 2
    assert kinds.count("launcher_started") == 2
    assert "downloading" in kinds and "update_done" in kinds
    started = [e for e in events if e.kind == "client_started"]
    assert [e.pid for e in started] == [7136, 26840, 10640, 17572]
    assert started[0].timestamp is not None and started[0].timestamp.hour == 8
    launch = next(e for e in events if e.kind == "launch_command")
    assert launch.detail == "ss14s://lizard.spacestation14.io/server"
    connect = next(e for e in events if e.kind == "connect_command")
    assert connect.detail == "ss14s://lizard.spacestation14.io/server"


def test_launcher_line_variants() -> None:
    assert parse_launcher_line("garbage") is None
    assert parse_launcher_line("2026-09-26 09:22:17.588 +10:00 [INF] Seeking connection to X") is None
    drop = parse_launcher_line(
        "2026-09-26 09:22:17.588 +10:00 [WRN] Dropping connect command: Busy connecting to a server"
    )
    assert drop is not None and drop.kind == "dropping" and drop.detail == "Busy connecting to a server"
    failed = parse_launcher_line("2026-09-26 09:22:17.588 +10:00 [ERR] Failed to connect: ConnectionFailed")
    assert failed is not None and failed.kind == "failed_to_connect" and failed.detail == "ConnectionFailed"


def test_log_tail_follows_growth_and_recreation(tmp_path: Path) -> None:
    path = tmp_path / "client.stdout.log"
    tail = LogTail(path)
    assert tail.read_new() == []
    path.write_bytes(b"line one\nline two\npartial")
    assert tail.read_new() == ["line one", "line two"]
    with path.open("ab") as fh:
        fh.write(b" finished\r\nthree\n")
    assert tail.read_new() == ["partial finished", "three"]
    assert tail.read_new() == []
    path.write_bytes(b"new file\n")  # smaller: recreated
    assert tail.read_new() == ["new file"]
    tail.reset()
    assert tail.read_new() == ["new file"]
    end_tail = LogTail(path, start_at_end=True)
    assert end_tail.read_new() == []
    with path.open("ab") as fh:
        fh.write(b"after\n")
    assert end_tail.read_new() == ["after"]


def test_launcher_log_tail_rolls_to_new_day(tmp_path: Path) -> None:
    (tmp_path / "launcher-20260925.log").write_text(
        "2026-09-25 10:00:00.000 +10:00 [DBG] Setting up manual-pipe logging for new client with PID 1.\n"
    )
    tail = LauncherLogTail(tmp_path, start_at_end=False)
    assert [e.pid for e in tail.read_new()] == [1]
    with (tmp_path / "launcher-20260925.log").open("a") as fh:
        fh.write("2026-09-25 10:00:01.000 +10:00 [DBG] EOF, ending pipe logging for 1.\n")
    assert [e.kind for e in tail.read_new()] == ["client_exited"]
    (tmp_path / "launcher-20260926.log").write_text(
        "2026-09-26 09:00:00.000 +10:00 [DBG] Setting up manual-pipe logging for new client with PID 2.\n"
    )
    assert [e.pid for e in tail.read_new()] == [2]
    assert LauncherLogTail(tmp_path / "missing").read_new() == []
    at_end = LauncherLogTail(tmp_path)
    assert at_end.read_new() == []
