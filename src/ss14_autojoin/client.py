"""Read what the game client and the launcher log, and tail those files.

Line formats and the meaning of each marker are verified against Jacob's logs in ``docs/fixtures/`` and the
engine source; see ``docs/ss14-launcher-reference.md`` sections 10 and 11a. Nothing here touches processes.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------------------------------------------
# client.stdout.log
# ---------------------------------------------------------------------------------------------------------------

_CLIENT_LINE = re.compile(r"^\[(?P<level>[A-Z]{4})\] (?P<sawmill>[^:\s]+): (?P<message>.*)$")
_STATUS_CHANGED = re.compile(r'^"(?P<endpoint>[^"]+)": Status changed to (?P<status>\w+), reason: "(?P<reason>.*)"$')
_RUNLEVEL = re.compile(r"^Runlevel changed to: (?P<level>\w+)$")
_ATTEMPT = re.compile(r"^Attempting to connect to (?P<host>\S+) port (?P<port>\d+)$")
_HANDSHAKE_EXCEPTION = "Exception during handshake:"
_HANDSHAKE_DONE = "Handshake completed, connection established."
_LIDGREN_PREFIX = "Disconnected: "
_DENIED_PREFIX = "Connect denied: "

FULL_MARKERS = ("server is full",)
"""Substrings (lower case) of a denial that mean "try again later" rather than "you are not allowed"."""


@dataclass(frozen=True, slots=True)
class DenyReason:
    """A decoded disconnect or denial reason (engine ``NetDisconnectMessage``)."""

    text: str
    redial: bool = False
    delay: float | None = None
    raw: str = ""

    @property
    def is_full(self) -> bool:
        lowered = self.text.lower()
        return any(marker in lowered for marker in FULL_MARKERS)

    @property
    def retryable(self) -> bool:
        """Only a full server is worth another attempt; bans, whitelists and bunkers are not."""
        return self.is_full

    @classmethod
    def parse(cls, raw: str) -> DenyReason:
        """Decode the quoted, possibly backslash-escaped JSON the client logs; fall back to the plain text."""
        text = raw.strip()
        if text.startswith(_LIDGREN_PREFIX):
            text = text[len(_LIDGREN_PREFIX) :]
        candidate = text.replace('\\"', '"')
        if candidate.startswith("{"):
            try:
                data = json.loads(candidate)
            except ValueError:
                data = None
            if isinstance(data, dict):
                reason = str(data.get("reason", "unknown reason"))
                delay = data.get("delay")
                return cls(
                    text=reason.removeprefix(_DENIED_PREFIX),
                    redial=bool(data.get("redial", False)),
                    delay=float(delay) if isinstance(delay, int | float) and not isinstance(delay, bool) else None,
                    raw=raw,
                )
        return cls(text=text.removeprefix(_DENIED_PREFIX), raw=raw)


@dataclass(slots=True)
class ClientLogState:
    """What one client's stdout says so far about its connection attempt.

    Feed lines in order; read ``outcome``: ``pending`` (nothing decisive yet), ``joined`` (the engine handshake
    completed or the run level reached Connected/InGame), ``failed`` (the winning connection was dropped before
    the handshake, the handshake threw, or the client fell back to Initialize). ``deny`` holds the decoded
    reason when the server gave one.
    """

    outcome: str = "pending"
    connecting: bool = False
    host: str | None = None
    port: int | None = None
    initiated: set[str] = field(default_factory=set)
    dropped: set[str] = field(default_factory=set)
    winning_endpoint: str | None = None
    deny: DenyReason | None = None
    disconnected_after_join: DenyReason | None = None
    exited: bool = False
    runlevel: str | None = None
    lines_seen: int = 0

    def feed(self, line: str) -> None:
        self.lines_seen += 1
        match = _CLIENT_LINE.match(line.rstrip("\r\n"))
        if not match:
            return
        sawmill, message = match.group("sawmill"), match.group("message")
        if sawmill == "net":
            self._feed_net(message)
        elif sawmill == "client":
            if (m := _RUNLEVEL.match(message)) is not None:
                self._feed_runlevel(m.group("level"))
        elif sawmill == "game" and (message.startswith("Shutting down!") or message == "Goodbye"):
            self.exited = True

    def feed_lines(self, lines: list[str] | str) -> None:
        for line in lines.splitlines() if isinstance(lines, str) else lines:
            self.feed(line)

    def _feed_net(self, message: str) -> None:
        if (m := _ATTEMPT.match(message)) is not None:
            self.connecting = True
            self.host, self.port = m.group("host"), int(m.group("port"))
            return
        if (m := _STATUS_CHANGED.match(message)) is not None:
            endpoint, status, reason = m.group("endpoint"), m.group("status"), m.group("reason")
            if status == "InitiatedConnect":
                self.initiated.add(endpoint)
            elif status == "Connected":
                self.winning_endpoint = endpoint
            elif status == "Disconnected":
                self.dropped.add(endpoint)
                decoded = DenyReason.parse(reason)
                if self.outcome == "joined":
                    self.disconnected_after_join = decoded
                elif endpoint == self.winning_endpoint:
                    self._fail(decoded)
                elif self.winning_endpoint is None and self.initiated and self.initiated <= self.dropped:
                    self._fail(decoded)  # every candidate address failed (unreachable server)
            return
        if message == _HANDSHAKE_DONE:
            self._join()
        elif message.startswith(_HANDSHAKE_EXCEPTION):
            _, _, tail = message.partition(_LIDGREN_PREFIX)
            decoded = DenyReason.parse(tail) if tail else DenyReason(text=message[len(_HANDSHAKE_EXCEPTION) :].strip())
            self._fail(decoded)

    def _feed_runlevel(self, level: str) -> None:
        self.runlevel = level
        if level in ("Connected", "InGame"):
            self._join()
        elif level == "Initialize" and self.connecting and self.outcome != "joined":
            self._fail(None)

    def _join(self) -> None:
        if self.outcome != "joined":
            self.outcome = "joined"

    def _fail(self, reason: DenyReason | None) -> None:
        if self.outcome == "joined":
            return
        self.outcome = "failed"
        if reason is not None and (self.deny is None or self.deny.text in ("", "unknown reason")):
            self.deny = reason

    @property
    def connecting_or_later(self) -> bool:
        """True once the client has at least started connecting (so a missing socket means something)."""
        return self.connecting or self.outcome != "pending" or bool(self.initiated)

    @property
    def summary(self) -> str:
        if self.outcome == "joined":
            return "joined" + (
                f", later disconnected: {self.disconnected_after_join.text}" if self.disconnected_after_join else ""
            )
        if self.outcome == "failed":
            return f"failed: {self.deny.text if self.deny else 'no reason logged'}"
        return "connecting" if self.connecting else "starting"


def parse_client_log(text: str) -> ClientLogState:
    state = ClientLogState()
    state.feed_lines(text)
    return state


# ---------------------------------------------------------------------------------------------------------------
# launcher-YYYYMMDD.log
# ---------------------------------------------------------------------------------------------------------------

_LAUNCHER_LINE = re.compile(
    r"^(?P<ts>\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} [+-]\d\d:\d\d) \[(?P<level>[A-Z]{3})\] (?P<message>.*)$"
)
_CONNECT_COMMAND = re.compile(r'^Connect command: "(?P<uri>[^"]*)", "(?P<reason>[^"]*)"$')
_DROPPING = re.compile(r"^Dropping connect command: (?P<why>.*)$")
_FAILED = re.compile(r"^Failed to connect: (?P<status>\w+)$")
_LAUNCH = re.compile(r"^Launch command: (?P<loader>.+?) \[0\] (?P<rest>.*)$")
_SS14_ADDRESS = re.compile(r"--ss14-address \[\d+\] (?P<address>\S+)")
_PID_START = re.compile(r"^Setting up manual-pipe logging for new client with PID (?P<pid>\d+)\.$")
_PID_EOF = re.compile(r"^EOF, ending pipe logging for (?P<pid>\d+)\.$")
_LAUNCHER_VERSION = re.compile(r"^Launcher version: (?P<version>\S+)$")


@dataclass(frozen=True, slots=True)
class LauncherEvent:
    """One interesting launcher log line."""

    kind: str
    """``connect_command``, ``dropping``, ``failed_to_connect``, ``update_done``, ``launch_command``,
    ``client_started``, ``client_exited``, ``launcher_started``, ``downloading``."""
    timestamp: datetime | None
    detail: str = ""
    pid: int | None = None


def parse_launcher_line(line: str) -> LauncherEvent | None:
    match = _LAUNCHER_LINE.match(line.rstrip("\r\n"))
    if not match:
        return None
    message = match.group("message")
    try:
        ts: datetime | None = datetime.strptime(match.group("ts"), "%Y-%m-%d %H:%M:%S.%f %z")
    except ValueError:
        ts = None
    if (m := _PID_START.match(message)) is not None:
        return LauncherEvent("client_started", ts, pid=int(m.group("pid")))
    if (m := _PID_EOF.match(message)) is not None:
        return LauncherEvent("client_exited", ts, pid=int(m.group("pid")))
    if (m := _CONNECT_COMMAND.match(message)) is not None:
        return LauncherEvent("connect_command", ts, m.group("uri"))
    if (m := _DROPPING.match(message)) is not None:
        return LauncherEvent("dropping", ts, m.group("why"))
    if (m := _FAILED.match(message)) is not None:
        return LauncherEvent("failed_to_connect", ts, m.group("status"))
    if message == "Update done!":
        return LauncherEvent("update_done", ts)
    if message.startswith("Missing ") and "downloading from" in message:
        return LauncherEvent("downloading", ts, message)
    if (m := _LAUNCH.match(message)) is not None:
        address = _SS14_ADDRESS.search(m.group("rest"))
        return LauncherEvent("launch_command", ts, address.group("address") if address else m.group("loader"))
    if (m := _LAUNCHER_VERSION.match(message)) is not None:
        return LauncherEvent("launcher_started", ts, m.group("version"))
    return None


def parse_launcher_log(text: str) -> list[LauncherEvent]:
    return [event for line in text.splitlines() if (event := parse_launcher_line(line)) is not None]


# ---------------------------------------------------------------------------------------------------------------
# tailing files that grow, get recreated (client.stdout.log) or roll daily (launcher-YYYYMMDD.log)
# ---------------------------------------------------------------------------------------------------------------


class LogTail:
    """Return the complete new lines of a file since the last call; start over when the file is replaced.

    Replacement is detected by a smaller size or a changed identity (inode / creation time), since the
    launcher recreates ``client.stdout.log`` at every client start. A trailing partial line is held back
    until its newline arrives (the launcher writes in 4 KiB chunks, so lines are cut anywhere).
    """

    def __init__(self, path: Path, start_at_end: bool = False) -> None:
        self.path = Path(path)
        self._offset = 0
        self._partial = b""
        self._identity: tuple[int, float] | None = None
        if start_at_end:
            try:
                st = self.path.stat()
            except OSError:
                return
            self._offset = st.st_size
            self._identity = _identity(st)

    def reset(self) -> None:
        self._offset, self._partial, self._identity = 0, b"", None

    def read_new(self) -> list[str]:
        try:
            st = self.path.stat()
        except OSError:
            return []
        identity = _identity(st)
        if st.st_size < self._offset or (self._identity is not None and identity != self._identity):
            self.reset()
        self._identity = identity
        if st.st_size == self._offset:
            return []
        try:
            with self.path.open("rb") as fh:
                fh.seek(self._offset)
                chunk = fh.read()
        except OSError:
            return []
        self._offset += len(chunk)
        data = self._partial + chunk
        *complete, self._partial = data.split(b"\n")
        return [line.decode("utf-8", errors="replace").rstrip("\r") for line in complete]


class LauncherLogTail:
    """Tail today's ``launcher-YYYYMMDD.log``, following the roll to a new day's file."""

    def __init__(self, log_dir: Path, start_at_end: bool = True) -> None:
        self.log_dir = Path(log_dir)
        self._tail: LogTail | None = None
        self._start_at_end = start_at_end

    def current_path(self) -> Path | None:
        files = sorted(self.log_dir.glob("launcher-*.log")) if self.log_dir.is_dir() else []
        return files[-1] if files else None

    def read_new(self) -> list[LauncherEvent]:
        path = self.current_path()
        if path is None:
            return []
        if self._tail is None or self._tail.path != path:
            self._tail = LogTail(path, start_at_end=self._start_at_end and self._tail is None)
        return [event for line in self._tail.read_new() if (event := parse_launcher_line(line)) is not None]


def _identity(st) -> tuple[int, float]:
    """Inode plus creation time where the platform has one (Windows, macOS); ctime is not usable, it moves on append."""
    birth = getattr(st, "st_birthtime", None)
    return (st.st_ino, float(birth) if birth is not None else 0.0)
