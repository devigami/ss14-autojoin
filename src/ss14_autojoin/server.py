"""Server addresses and the ``/status`` endpoint.

Mirrors the launcher's ``UriHelper`` (SS14.Launcher, commit 437fe66) so the tool computes the same URLs the
launcher does, and parses the status JSON the content's ``ServerGameTicker.StatusShell`` produces. Facts and
test vectors: ``docs/ss14-launcher-reference.md`` sections 1 and 2.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from . import __version__

DEFAULT_PORT = 1212
"""Default HTTP API (and UDP game) port of an ``ss14://`` address (launcher ``Global.DefaultServerPort``)."""

STATUS_TIMEOUT = 5.0
"""Seconds the launcher waits for ``/status`` before calling a server offline."""

USER_AGENT = f"ss14-autojoin/{__version__}"

_SCHEMES = ("ss14", "ss14s")
_HTTP_DEFAULT_PORTS = {"http": 80, "https": 443}


class AddressError(ValueError):
    """The text is not a valid ``ss14://`` or ``ss14s://`` address."""


class ServerUnreachable(Exception):
    """``/status`` could not be fetched or parsed; the launcher would show the server as offline."""

    def __init__(self, address: ServerAddress, cause: Exception) -> None:
        super().__init__(f"{address.status_url}: {cause}")
        self.address = address
        self.cause = cause


@dataclass(frozen=True, slots=True)
class ServerAddress:
    """An ``ss14://`` or ``ss14s://`` server address, parsed the way the launcher parses it."""

    scheme: str
    host: str
    port: int | None
    path: str

    @classmethod
    def parse(cls, text: str) -> ServerAddress:
        """Parse ``host``, ``host:port``, ``ss14://host[:port][/path]`` or ``ss14s://...``.

        Like the launcher, text without ``://`` gets ``ss14://`` prepended; any other scheme or an empty host is
        rejected.
        """
        text = text.strip()
        if "://" not in text:
            text = "ss14://" + text
        parts = urlsplit(text)
        if parts.scheme not in _SCHEMES:
            raise AddressError(f"not an ss14:// or ss14s:// address: {text!r}")
        if not parts.hostname:
            raise AddressError(f"address has no host: {text!r}")
        try:
            port = parts.port
        except ValueError as e:
            raise AddressError(f"invalid port in {text!r}") from e
        return cls(parts.scheme, parts.hostname, port, parts.path)

    @property
    def uri(self) -> str:
        """The address to hand to the launcher: ``ss14://host[:port][/path]``."""
        return f"{self.scheme}://{self._authority(self.port)}{self.path}"

    @property
    def api_base(self) -> str:
        """``http(s)://host[:port]/path/`` exactly as ``UriHelper.GetServerApiAddress`` builds it.

        ``ss14`` maps to ``http`` with port 1212 unless one is given; ``ss14s`` maps to ``https`` (443 implied).
        Like .NET's ``UriBuilder``, a port equal to the HTTP scheme's default is left out.
        """
        http_scheme = "https" if self.scheme == "ss14s" else "http"
        port = self.port
        if port is None and self.scheme == "ss14":
            port = DEFAULT_PORT
        if port == _HTTP_DEFAULT_PORTS[http_scheme]:
            port = None
        path = self.path if self.path.endswith("/") else self.path + "/"
        return f"{http_scheme}://{self._authority(port)}{path}"

    @property
    def status_url(self) -> str:
        return self.api_base + "status"

    @property
    def info_url(self) -> str:
        return self.api_base + "info"

    def _authority(self, port: int | None) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return host if port is None else f"{host}:{port}"

    def __str__(self) -> str:
        return self.uri


class RunLevel(IntEnum):
    """``run_level`` in ``/status`` (content ``GameRunLevel``)."""

    PRE_ROUND_LOBBY = 0
    IN_ROUND = 1
    POST_ROUND = 2


@dataclass(frozen=True, slots=True)
class ServerStatus:
    """One ``/status`` response. ``players`` already excludes admins unless the server counts them."""

    name: str | None
    players: int
    soft_max_players: int | None
    run_level: RunLevel | None
    round_id: int | None
    map: str | None
    preset: str | None
    panic_bunker: bool
    round_start_time: str | None
    tags: tuple[str, ...]
    raw: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ServerStatus:
        run_level_value = _opt_int(data, "run_level")
        try:
            run_level = RunLevel(run_level_value) if run_level_value is not None else None
        except ValueError:
            run_level = None
        soft_max = _opt_int(data, "soft_max_players")
        tags = data.get("tags")
        return cls(
            name=_opt_str(data, "name"),
            players=max(0, _opt_int(data, "players") or 0),
            soft_max_players=max(0, soft_max) if soft_max is not None else None,
            run_level=run_level,
            round_id=_opt_int(data, "round_id"),
            map=_opt_str(data, "map"),
            preset=_opt_str(data, "preset"),
            panic_bunker=bool(data.get("panic_bunker", False)),
            round_start_time=_opt_str(data, "round_start_time"),
            tags=tuple(str(t) for t in tags) if isinstance(tags, list) else (),
            raw=dict(data),
        )

    @property
    def free_slots(self) -> int | None:
        """Slots left under the soft cap, or ``None`` when the server reports no cap (missing or 0)."""
        if not self.soft_max_players:
            return None
        return self.soft_max_players - self.players

    def has_free_slot(self, margin: int = 0) -> bool:
        """True when ``players < soft_max_players - margin``; a server without a cap always has room."""
        free = self.free_slots
        return True if free is None else free > margin


def fetch_status(address: ServerAddress | str, timeout: float = STATUS_TIMEOUT) -> ServerStatus:
    """GET ``/status`` and parse it; raise :class:`ServerUnreachable` on any transport or format problem."""
    if isinstance(address, str):
        address = ServerAddress.parse(address)
    request = Request(address.status_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - scheme is fixed to http(s) above
            body = response.read()
    except (URLError, OSError) as e:
        raise ServerUnreachable(address, e) from e
    try:
        data = json.loads(body)
    except ValueError as e:
        raise ServerUnreachable(address, e) from e
    if not isinstance(data, dict):
        raise ServerUnreachable(address, ValueError("status body is not a JSON object"))
    return ServerStatus.from_json(data)


def _opt_int(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return int(value)


def _opt_str(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    return value if isinstance(value, str) else None
