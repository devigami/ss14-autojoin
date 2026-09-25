from __future__ import annotations

from collections import deque
from pathlib import Path

from ss14_autojoin.client import LauncherEvent
from ss14_autojoin.joiner import Joiner, JoinerConfig, Phase
from ss14_autojoin.server import ServerAddress, ServerStatus, ServerUnreachable

FIXTURES = Path(__file__).resolve().parent.parent / "docs" / "fixtures"
ADDRESS = ServerAddress.parse("ss14s://lizard.spacestation14.io/server")
JOINED_LINES = (FIXTURES / "client.stdout.joined.log").read_text().splitlines()
FULL_LINES = (FIXTURES / "client.stdout.full-after-exit.log").read_text().splitlines()
TRUNCATED_LINES = (FIXTURES / "client.stdout.full.log").read_text().splitlines()


def status(players: int, cap: int = 80, **extra) -> ServerStatus:
    return ServerStatus.from_json(
        {"name": "Lizard", "players": players, "soft_max_players": cap, "run_level": 1, **extra}
    )


class FakePorts:
    """Scripted world: statuses per poll, and per connect a script of what the launcher and client do."""

    def __init__(self, statuses, scripts) -> None:
        self.statuses = deque(statuses)
        self.scripts = deque(scripts)
        self.time = 1000.0
        self.connects: list[str] = []
        self.terminated: list[int] = []
        self.restarts: list[str] = []
        self.events: deque[LauncherEvent] = deque()
        self.lines: deque[str] = deque()
        self.alive: set[int] = set()
        self.resets = 0
        self.after_exit: deque[list[str]] = deque()
        self.script: dict | None = None

    # ports
    def now(self) -> float:
        return self.time

    def sleep(self, seconds: float) -> None:
        self.time += seconds
        self._advance()

    def fetch_status(self, address):
        item = self.statuses.popleft() if len(self.statuses) > 1 else self.statuses[0]
        if item is None:
            raise ServerUnreachable(address, ConnectionRefusedError("refused"))
        return item

    def send_connect(self, uri: str) -> None:
        self.connects.append(uri)
        self.script = dict(self.scripts.popleft()) if self.scripts else {}
        self.script.setdefault("connect_at", self.time)

    def launcher_events(self):
        out = list(self.events)
        self.events.clear()
        return out

    def client_lines(self):
        out = list(self.lines)
        self.lines.clear()
        return out

    def reset_client_log(self) -> None:
        self.resets += 1

    def process_alive(self, pid: int) -> bool:
        return pid in self.alive

    def terminate(self, pid: int) -> None:
        self.terminated.append(pid)
        self.alive.discard(pid)
        self.events.append(LauncherEvent("client_exited", None, pid=pid))
        if self.script and self.script.get("post_mortem"):
            self.lines.extend(self.script.pop("post_mortem"))

    def restart_launcher(self, uri: str) -> None:
        self.restarts.append(uri)
        self.script = {"pid": 999, "pid_after": 3, "lines": JOINED_LINES, "connect_at": self.time}

    # scripted world advancing with time
    def _advance(self) -> None:
        s = self.script
        if not s:
            return
        elapsed = self.time - s["connect_at"]
        if "drop_after" in s and elapsed >= s["drop_after"]:
            self.events.append(LauncherEvent("dropping", None, "Busy connecting to a server"))
            s.pop("drop_after")
        if "pid_after" in s and elapsed >= s["pid_after"]:
            pid = s["pid"]
            self.alive.add(pid)
            self.events.append(LauncherEvent("client_started", None, pid=pid))
            s["lines_at"] = self.time + s.get("lines_delay", 2)
            s.pop("pid_after")
        if "lines_at" in s and self.time >= s["lines_at"]:
            self.lines.extend(s.get("lines", []))
            s.pop("lines_at")
            if s.get("exit_after_lines"):
                self.alive.discard(s["pid"])
                self.events.append(LauncherEvent("client_exited", None, pid=s["pid"]))


def make(ports, **overrides) -> Joiner:
    config = JoinerConfig(address=ADDRESS, cooldown=1, **overrides)
    log: list[tuple[str, str]] = []
    joiner = Joiner(config, ports, listener=lambda kind, msg: log.append((kind, msg)))
    joiner.events_log = log  # type: ignore[attr-defined]
    return joiner


def test_joins_when_a_slot_opens() -> None:
    ports = FakePorts([status(80), status(80), status(79)], [{"pid": 7136, "pid_after": 3, "lines": JOINED_LINES}])
    joiner = make(ports)
    outcome = joiner.run()
    assert outcome.success and outcome.attempts == 1
    assert ports.connects == [ADDRESS.uri] and ports.resets == 1
    assert ports.terminated == []
    kinds = [k for k, _ in joiner.events_log]
    assert kinds.count("attempt") == 1 and "joined" in kinds and kinds[-1] == "stop"
    assert joiner.attempts[0].pid == 7136 and joiner.attempts[0].outcome == "joined"


def test_full_denial_is_retried_then_joins() -> None:
    ports = FakePorts(
        [status(79)],
        [{"pid": 1, "pid_after": 3, "lines": FULL_LINES[:-5]}, {"pid": 2, "pid_after": 3, "lines": JOINED_LINES}],
    )
    joiner = make(ports)
    outcome = joiner.run()
    assert outcome.success and outcome.attempts == 2
    assert ports.terminated == [1]
    first = joiner.attempts[0]
    assert first.outcome == "failed" and first.deny is not None and first.deny.is_full
    assert joiner.unknown_failures == 0


def test_timeout_then_post_mortem_reason_stops_on_ban() -> None:
    ban = [
        "[DEBG] net: Attempting to connect to lizard.spacestation14.com port 1212",
        '[DEBG] net: "1.2.3.4:1212": Status changed to InitiatedConnect, reason: "user called connect"',
        '[DEBG] net: "1.2.3.4:1212": Status changed to Connected, reason: "Connected to X"',
        '[DEBG] net: "1.2.3.4:1212": Status changed to Disconnected, reason: '
        '"{\\"reason\\":\\"Connect denied: You are banned.\\",\\"redial\\":false}"',
    ]
    ports = FakePorts([status(70)], [{"pid": 5, "pid_after": 2, "lines": TRUNCATED_LINES, "post_mortem": ban}])
    joiner = make(ports, attempt_timeout=10)
    outcome = joiner.run()
    assert not outcome.success and "You are banned." in outcome.message
    assert ports.terminated == [5]
    assert joiner.attempts[0].reason.startswith("failed: You are banned.")


def test_timeout_without_reason_counts_as_unknown_and_eventually_stops() -> None:
    scripts = [{"pid": 10 + i, "pid_after": 2, "lines": TRUNCATED_LINES} for i in range(3)]
    ports = FakePorts([status(70)], scripts)
    joiner = make(ports, attempt_timeout=5, max_unknown_failures=3)
    outcome = joiner.run()
    assert not outcome.success and "3 failures without a readable reason" in outcome.message
    assert ports.terminated == [10, 11, 12]
    assert all(a.reason == "no join within the attempt timeout" for a in joiner.attempts)


def test_no_client_appears_is_a_failure_and_the_loop_continues() -> None:
    ports = FakePorts([status(70)], [{}, {"pid": 3, "pid_after": 1, "lines": JOINED_LINES}])
    joiner = make(ports, connect_timeout=5)
    outcome = joiner.run()
    assert outcome.success and outcome.attempts == 2
    assert joiner.attempts[0].reason == "no client appeared after the connect command"


def test_dropped_command_stops_unless_restart_enabled() -> None:
    ports = FakePorts([status(70)], [{"drop_after": 1}])
    outcome = make(ports).run()
    assert not outcome.success and "drops connect commands" in outcome.message

    ports = FakePorts([status(70)], [{"drop_after": 1}])
    outcome = make(ports, restart_launcher=True).run()
    assert outcome.success and ports.restarts == [ADDRESS.uri]


def test_offline_server_backs_off_and_max_attempts() -> None:
    ports = FakePorts([None, None, status(70)], [{"pid": 1, "pid_after": 1, "lines": FULL_LINES}])
    joiner = make(ports, offline_interval=7, max_attempts=1)
    outcome = joiner.run()
    assert not outcome.success and "gave up after 1 attempts" in outcome.message
    statuses = [m for k, m in joiner.events_log if k == "status"]
    assert statuses[0].startswith("offline:")
    assert ports.time >= 1000 + 2 * 7


def test_panic_bunker_filter_and_stop_request() -> None:
    ports = FakePorts([status(70, panic_bunker=True)], [])
    joiner = make(ports, skip_panic_bunker=True)
    joiner.step()
    assert joiner.phase is Phase.WATCHING and ports.connects == []
    joiner.stop()
    outcome = joiner.run()
    assert not outcome.success and outcome.message == "stopped by user"


def test_rejoin_watches_the_client_and_starts_over() -> None:
    kicked = JOINED_LINES + [
        '[DEBG] net: "51.81.194.242:1212": Status changed to Disconnected, '
        'reason: "Disconnected: {\\"reason\\":\\"Kicked\\"}"'
    ]
    ports = FakePorts(
        [status(70)],
        [
            {"pid": 1, "pid_after": 1, "lines": kicked},
            {"pid": 2, "pid_after": 1, "lines": JOINED_LINES, "exit_after_lines": True},
        ],
    )
    joiner = make(ports, rejoin=True, max_attempts=2)
    outcome = joiner.run()
    assert outcome.attempts == 2
    assert ports.terminated == [1]
    assert joiner.attempts[0].outcome == "disconnected"
    assert joiner.attempts[1].outcome == "joined"
    assert "gave up after 2 attempts" in outcome.message
