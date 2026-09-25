from __future__ import annotations

import socket

import pytest

from ss14_autojoin.server import (
    DEFAULT_PORT,
    AddressError,
    RunLevel,
    ServerAddress,
    ServerStatus,
    ServerUnreachable,
    fetch_status,
)
from tests.conftest import STATUS_FULL, FakeStatusServer

# The launcher's own UriHelperTests (SS14.Launcher.Tests/UriHelperTests.cs).
LAUNCHER_VECTORS = [
    ("server.spacestation14.io", "http://server.spacestation14.io:1212/status"),
    ("ss14s://server.spacestation14.io", "https://server.spacestation14.io/status"),
    ("ss14s://server.spacestation14.io:1212", "https://server.spacestation14.io:1212/status"),
    ("ss14s://server.spacestation14.io/foo", "https://server.spacestation14.io/foo/status"),
    # Wizard's Den Lizard as the launcher stores it (Jacob's launcher log, 2026-09-26).
    ("ss14s://lizard.spacestation14.io/server", "https://lizard.spacestation14.io/server/status"),
]


@pytest.mark.parametrize(("text", "expected"), LAUNCHER_VECTORS)
def test_status_url_matches_launcher(text: str, expected: str) -> None:
    assert ServerAddress.parse(text).status_url == expected


@pytest.mark.parametrize(
    ("text", "uri", "api_base"),
    [
        ("host", "ss14://host", "http://host:1212/"),
        ("ss14://host:1212", "ss14://host:1212", "http://host:1212/"),
        ("ss14://host:4000/", "ss14://host:4000/", "http://host:4000/"),
        ("ss14://HOST.Example.org", "ss14://host.example.org", "http://host.example.org:1212/"),
        ("ss14s://host:443", "ss14s://host:443", "https://host/"),
        ("ss14://host:80", "ss14://host:80", "http://host/"),
        ("ss14://[::1]:1212", "ss14://[::1]:1212", "http://[::1]:1212/"),
        ("  ss14://host  ", "ss14://host", "http://host:1212/"),
    ],
)
def test_parse_round_trip(text: str, uri: str, api_base: str) -> None:
    address = ServerAddress.parse(text)
    assert address.uri == uri
    assert str(address) == uri
    assert address.api_base == api_base
    assert address.info_url == api_base + "info"


def test_default_port_is_1212() -> None:
    assert DEFAULT_PORT == 1212
    assert ServerAddress.parse("host").port is None


@pytest.mark.parametrize("text", ["http://host", "ss14://", "ss14://:1212", "ss14://host:abc", "ss14://host:99999", ""])
def test_parse_rejects_invalid(text: str) -> None:
    with pytest.raises(AddressError):
        ServerAddress.parse(text)


def test_status_from_full_json() -> None:
    status = ServerStatus.from_json(STATUS_FULL)
    assert status.name == "Wizard's Den Lizard [NA West]"
    assert status.players == 80
    assert status.soft_max_players == 80
    assert status.run_level is RunLevel.IN_ROUND
    assert status.round_id == 12345
    assert status.map == "Box"
    assert status.preset == "Secret"
    assert status.panic_bunker is False
    assert status.round_start_time == "2026-09-25T09:00:00.0000000Z"
    assert status.tags == ("region:am_n_w", "rp:low")
    assert status.raw == STATUS_FULL
    assert status.free_slots == 0
    assert not status.has_free_slot()


def test_status_from_minimal_engine_json() -> None:
    status = ServerStatus.from_json({"name": "bare", "players": 3})
    assert status.soft_max_players is None
    assert status.run_level is None
    assert status.free_slots is None
    assert status.has_free_slot()
    assert status.has_free_slot(margin=5)
    assert status.tags == ()


def test_status_tolerates_bad_values() -> None:
    status = ServerStatus.from_json(
        {"players": -4, "soft_max_players": -1, "run_level": 7, "tags": "nope", "round_id": "12", "name": 5}
    )
    assert status.players == 0
    assert status.soft_max_players == 0
    assert status.free_slots is None
    assert status.run_level is None
    assert status.tags == ()
    assert status.round_id is None
    assert status.name is None


@pytest.mark.parametrize(
    ("players", "cap", "margin", "expected"),
    [
        (78, 80, 0, True),
        (79, 80, 0, True),
        (80, 80, 0, False),
        (81, 80, 0, False),
        (78, 80, 1, True),
        (78, 80, 2, False),
    ],
)
def test_has_free_slot_margin(players: int, cap: int, margin: int, expected: bool) -> None:
    status = ServerStatus.from_json({"players": players, "soft_max_players": cap})
    assert status.has_free_slot(margin) is expected


def test_fetch_status_from_fake_server(fake_server: FakeStatusServer) -> None:
    status = fetch_status(fake_server.address)
    assert status.name == STATUS_FULL["name"]
    assert status.players == 80
    path, user_agent = fake_server.requests[-1]
    assert path == "/status"
    assert user_agent.startswith("ss14-autojoin/")


def test_fetch_status_sees_changes(fake_server: FakeStatusServer) -> None:
    fake_server.set_status({**STATUS_FULL, "players": 79})
    assert fetch_status(ServerAddress.parse(fake_server.address)).has_free_slot()


def test_fetch_status_http_error(fake_server: FakeStatusServer) -> None:
    fake_server.code = 503
    with pytest.raises(ServerUnreachable):
        fetch_status(fake_server.address)


def test_fetch_status_bad_json(fake_server: FakeStatusServer) -> None:
    fake_server.body = b"<html>not json</html>"
    with pytest.raises(ServerUnreachable):
        fetch_status(fake_server.address)
    fake_server.body = b"[1, 2, 3]"
    with pytest.raises(ServerUnreachable):
        fetch_status(fake_server.address)


def test_fetch_status_connection_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    with pytest.raises(ServerUnreachable) as info:
        fetch_status(f"ss14://127.0.0.1:{free_port}", timeout=2)
    assert info.value.address.port == free_port
