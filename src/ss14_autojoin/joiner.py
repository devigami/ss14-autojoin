"""The auto-join loop: watch, connect through the launcher, verify, clean up, repeat.

Everything that touches the machine comes in through :class:`Ports`, so the loop runs unchanged against fakes
in tests and against ``runtime.RealPorts`` on Windows. The design and the reasons behind each timeout are in
``docs/plan.md`` ("The state machine" and "Why this detection method").
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from .client import ClientLogState, DenyReason, LauncherEvent
from .server import ServerAddress, ServerStatus, ServerUnreachable


class Phase(enum.Enum):
    WATCHING = "watching"
    CONNECTING = "connecting"
    VERIFYING = "verifying"
    JOINED = "joined"
    FAILED = "failed"
    STUCK = "stuck"
    STOPPED = "stopped"


@dataclass(slots=True)
class JoinerConfig:
    address: ServerAddress
    interval: float = 3.0
    """Seconds between status polls while watching (never below 1)."""
    offline_interval: float = 10.0
    """Seconds between polls while the server is unreachable."""
    margin: int = 0
    """Require this many free slots beyond one before attempting."""
    tick: float = 1.0
    """Seconds between checks while connecting and verifying."""
    connect_timeout: float = 30.0
    """Seconds from the connect command until the launcher must have started a client."""
    update_timeout: float = 180.0
    """The connect timeout while the launcher is downloading content."""
    attempt_timeout: float = 60.0
    """Seconds from the client PID until the attempt is decided one way or the other."""
    socket_grace: float = 12.0
    """Seconds after the client PID before "no UDP socket" counts as a rejected connection."""
    confirm_after: float = 15.0
    """Seconds of an open UDP socket after the client PID that count as a join (the log may never flush)."""
    unknown_policy: str = "keep"
    """What to do when the attempt timeout passes without evidence either way: ``keep`` the client running
    and stop the tool (never kill a session that may be live), or ``retry`` (close it and try again)."""
    exit_grace: float = 10.0
    """Seconds to wait for a terminated client to be gone (and its log to flush)."""
    cooldown: float = 2.0
    """Seconds to wait after a failed attempt before watching again."""
    max_unknown_failures: int = 5
    """Stop after this many consecutive failures without a readable reason."""
    max_attempts: int | None = None
    """Stop after this many attempts (None: unlimited)."""
    rejoin: bool = False
    """After a join, keep watching the client and start over when it exits or is disconnected."""
    restart_launcher: bool = False
    """When the launcher drops connect commands (errored overlay), restart it with the address."""
    skip_panic_bunker: bool = False
    """Do not attempt while the server reports the panic bunker as enabled."""


class Ports(Protocol):
    """Everything the loop needs from the outside world."""

    def now(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...
    def fetch_status(self, address: ServerAddress) -> ServerStatus: ...
    def send_connect(self, uri: str) -> None: ...
    def launcher_events(self) -> list[LauncherEvent]: ...
    def client_lines(self) -> list[str]: ...
    def reset_client_log(self) -> None: ...
    def process_alive(self, pid: int) -> bool: ...
    def terminate(self, pid: int) -> None: ...
    def restart_launcher(self, uri: str) -> None: ...
    def client_udp_sockets(self, pid: int) -> int | None:
        """Open UDP sockets of the client, or None when that cannot be read."""
        ...


@dataclass(slots=True)
class Attempt:
    number: int
    started_at: float
    pid: int | None = None
    pid_at: float | None = None
    outcome: str = "pending"
    reason: str = ""
    deny: DenyReason | None = None
    log: ClientLogState = field(default_factory=ClientLogState)
    sockets_seen: int = 0
    """How many consecutive checks found at least one UDP socket open."""
    last_sockets: int | None = None


@dataclass(frozen=True, slots=True)
class Outcome:
    success: bool
    message: str
    attempts: int


Listener = Callable[[str, str], None]
"""``listener(kind, message)``: kinds are ``status``, ``attempt``, ``joined``, ``failed``, ``stuck``, ``stop``."""


class Joiner:
    def __init__(self, config: JoinerConfig, ports: Ports, listener: Listener | None = None) -> None:
        self.config = config
        self.ports = ports
        self.listener = listener or (lambda kind, message: None)
        self.phase = Phase.WATCHING
        self.attempts: list[Attempt] = []
        self.unknown_failures = 0
        self.last_status: ServerStatus | None = None
        self.stop_requested = False
        self._final: Outcome | None = None
        self._attempt: Attempt | None = None
        self._downloading = False
        self._last_key: tuple[str, int | None] | None = None

    # -- public --------------------------------------------------------------------------------------------------

    def run(self) -> Outcome:
        """Run until joined (unless ``rejoin``), stopped by a non-retryable reason, or :meth:`stop` was called."""
        while self._final is None:
            if self.stop_requested:
                self._finish(False, "stopped by user")
                break
            self.step()
        assert self._final is not None
        return self._final

    def stop(self) -> None:
        self.stop_requested = True

    def step(self) -> None:
        handler = {
            Phase.WATCHING: self._watch,
            Phase.CONNECTING: self._connecting,
            Phase.VERIFYING: self._verifying,
            Phase.FAILED: self._failed,
            Phase.JOINED: self._joined,
            Phase.STUCK: self._stuck,
        }.get(self.phase)
        if handler is not None:
            handler()

    # -- phases --------------------------------------------------------------------------------------------------

    def _watch(self) -> None:
        try:
            status = self.ports.fetch_status(self.config.address)
        except ServerUnreachable as e:
            self._status_line(("offline", None), f"offline: {e.cause}")
            self.ports.sleep(self.config.offline_interval)
            return
        self.last_status = status
        free = status.has_free_slot(self.config.margin)
        blocked = self.config.skip_panic_bunker and status.panic_bunker
        cap = status.soft_max_players if status.soft_max_players else "no cap"
        label = "slot free" if free and not blocked else ("panic bunker" if blocked else "full")
        self._status_line((label, status.players), f"{status.players}/{cap} players, {label}")
        if free and not blocked:
            self._start_attempt()
        else:
            self.ports.sleep(max(1.0, self.config.interval))

    def _start_attempt(self) -> None:
        if self.config.max_attempts is not None and len(self.attempts) >= self.config.max_attempts:
            self._finish(False, f"gave up after {len(self.attempts)} attempts")
            return
        self.ports.launcher_events()  # drop stale events so this attempt only sees its own
        self.ports.reset_client_log()
        attempt = Attempt(number=len(self.attempts) + 1, started_at=self.ports.now())
        self.attempts.append(attempt)
        self._attempt = attempt
        self._downloading = False
        self.listener(
            "attempt", f"attempt {attempt.number}: asking the launcher to connect to {self.config.address.uri}"
        )
        self.ports.send_connect(self.config.address.uri)
        self.phase = Phase.CONNECTING

    def _connecting(self) -> None:
        attempt = self._current()
        for event in self.ports.launcher_events():
            if event.kind == "downloading":
                self._downloading = True
                self.listener("status", "launcher is downloading server content")
            elif event.kind == "dropping":
                self.listener("stuck", f"launcher dropped the connect command: {event.detail}")
                self.phase = Phase.STUCK
                return
            elif event.kind == "failed_to_connect":
                self._fail_attempt(f"launcher: {event.detail}", None)
                return
            elif event.kind == "client_started" and event.pid is not None:
                attempt.pid, attempt.pid_at = event.pid, self.ports.now()
                self.listener("status", f"client started (pid {event.pid}), waiting for the join")
                self.phase = Phase.VERIFYING
                return
        timeout = self.config.update_timeout if self._downloading else self.config.connect_timeout
        if self.ports.now() - attempt.started_at > timeout:
            self._fail_attempt("no client appeared after the connect command", None)
            return
        self.ports.sleep(self.config.tick)

    def _verifying(self) -> None:
        attempt = self._current()
        assert attempt.pid is not None and attempt.pid_at is not None
        elapsed = self.ports.now() - attempt.pid_at
        attempt.log.feed_lines(self.ports.client_lines())
        exited = any(e.kind == "client_exited" and e.pid == attempt.pid for e in self.ports.launcher_events())
        if attempt.log.outcome == "joined":
            self._join(attempt, "the client log shows the handshake completed")
            return
        if attempt.log.outcome == "failed":
            self._fail_attempt(attempt.log.summary, attempt.log.deny)
            return
        if exited or not self.ports.process_alive(attempt.pid):
            attempt.log.feed_lines(self.ports.client_lines())  # the launcher flushes the log on exit
            if attempt.log.outcome == "joined":
                self._join(attempt, "the client log shows the handshake completed, but the client has exited")
                return
            reason = attempt.log.summary if attempt.log.outcome == "failed" else "client exited"
            self._fail_attempt(reason, attempt.log.deny)
            return
        # The log rarely flushes while the client is quiet, so the network is the second witness: a rejected
        # client closes its UDP sockets, a connected one keeps one open for the whole session.
        sockets = self._udp_sockets(attempt.pid)
        attempt.last_sockets = sockets
        if sockets is not None:
            attempt.sockets_seen = attempt.sockets_seen + 1 if sockets > 0 else 0
            if sockets == 0 and elapsed > self.config.socket_grace and attempt.log.connecting_or_later:
                self._fail_attempt("client closed its network sockets (connection rejected or lost)", None)
                return
            if sockets > 0 and elapsed > self.config.confirm_after and attempt.sockets_seen >= 3:
                self._join(attempt, f"client kept a UDP socket open for {elapsed:.0f} s")
                return
        if elapsed > self.config.attempt_timeout:
            if self.config.unknown_policy == "retry":
                self._fail_attempt("no join within the attempt timeout", None)
            else:
                attempt.outcome = "unknown"
                self._finish(
                    False,
                    f"stopped after {elapsed:.0f} s without evidence either way; the client (pid {attempt.pid}) "
                    "was left running so a live session is not lost. Check the game window.",
                )
            return
        self.ports.sleep(self.config.tick)

    def _join(self, attempt: Attempt, evidence: str) -> None:
        attempt.outcome = "joined"
        self.unknown_failures = 0
        self.listener("joined", f"joined {self.config.address.uri} on attempt {attempt.number} ({evidence})")
        self.phase = Phase.JOINED

    def _udp_sockets(self, pid: int) -> int | None:
        reader = getattr(self.ports, "client_udp_sockets", None)
        if reader is None:
            return None
        try:
            return reader(pid)
        except Exception:  # noqa: BLE001 - a broken probe must not stop the loop
            return None

    def _failed(self) -> None:
        attempt = self._current()
        if attempt.pid is not None:
            self._close_client(attempt)
        reason = attempt.deny
        if reason is not None and not reason.retryable:
            self._finish(False, f"stopped: the server refused the connection ({reason.text}); retrying will not help")
            return
        if reason is None:
            self.unknown_failures += 1
            if self.unknown_failures >= self.config.max_unknown_failures:
                self._finish(False, f"stopped after {self.unknown_failures} failures without a readable reason")
                return
        else:
            self.unknown_failures = 0
        self._attempt = None
        self.ports.sleep(self.config.cooldown)
        self.phase = Phase.WATCHING

    def _joined(self) -> None:
        attempt = self._current()
        if not self.config.rejoin:
            self._finish(True, f"joined on attempt {attempt.number}")
            return
        attempt.log.feed_lines(self.ports.client_lines())
        exited = attempt.pid is not None and (
            any(e.kind == "client_exited" and e.pid == attempt.pid for e in self.ports.launcher_events())
            or not self.ports.process_alive(attempt.pid)
        )
        if exited:
            self.listener("status", "client exited; watching again")
            self._attempt = None
            self.phase = Phase.WATCHING
            return
        if attempt.log.disconnected_after_join is not None:
            self.listener("status", f"disconnected: {attempt.log.disconnected_after_join.text}; closing the client")
            attempt.deny = attempt.log.disconnected_after_join
            attempt.outcome = "disconnected"
            self._close_client(attempt)
            self._attempt = None
            self.ports.sleep(self.config.cooldown)
            self.phase = Phase.WATCHING
            return
        self.ports.sleep(max(1.0, self.config.interval))

    def _stuck(self) -> None:
        attempt = self._current()
        if not self.config.restart_launcher:
            self._finish(
                False,
                "stopped: the launcher is showing an error and drops connect commands; dismiss it or enable restart",
            )
            return
        self.listener("stuck", "restarting the launcher with the server address")
        self.ports.restart_launcher(self.config.address.uri)
        attempt.started_at = self.ports.now()
        self.phase = Phase.CONNECTING

    # -- helpers -------------------------------------------------------------------------------------------------

    def _current(self) -> Attempt:
        assert self._attempt is not None, f"no attempt in phase {self.phase}"
        return self._attempt

    def _fail_attempt(self, reason: str, deny: DenyReason | None) -> None:
        attempt = self._current()
        attempt.outcome, attempt.reason, attempt.deny = "failed", reason, deny
        self.listener("failed", f"attempt {attempt.number} failed: {reason}")
        self.phase = Phase.FAILED

    def _close_client(self, attempt: Attempt) -> None:
        assert attempt.pid is not None
        if self.ports.process_alive(attempt.pid):
            self.listener("status", f"closing the game client (pid {attempt.pid})")
            self.ports.terminate(attempt.pid)
            deadline = self.ports.now() + self.config.exit_grace
            while self.ports.process_alive(attempt.pid) and self.ports.now() < deadline:
                self.ports.sleep(min(0.5, self.config.tick))
        # Post-mortem read: the launcher flushes the client log when the client exits.
        attempt.log.feed_lines(self.ports.client_lines())
        if attempt.deny is None and attempt.log.deny is not None:
            attempt.deny = attempt.log.deny
            attempt.reason = attempt.log.summary
            self.listener("status", f"reason read after exit: {attempt.log.deny.text}")

    def _status_line(self, key: tuple[str, int | None], message: str) -> None:
        if key != self._last_key:
            self._last_key = key
            self.listener("status", message)

    def _finish(self, success: bool, message: str) -> None:
        self._final = Outcome(success, message, len(self.attempts))
        self.phase = Phase.STOPPED
        self.listener("stop", message)
