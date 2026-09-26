"""Shared fixtures: a local fake SS14 status server so tests never touch the network."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

STATUS_FULL = {
    "name": "Wizard's Den Lizard [NA West]",
    "map": "Box",
    "round_id": 12345,
    "players": 80,
    "soft_max_players": 80,
    "panic_bunker": False,
    "run_level": 1,
    "preset": "Secret",
    "round_start_time": "2026-09-25T09:00:00.0000000Z",
    "tags": ["region:am_n_w", "rp:low"],
}


class FakeStatusServer:
    """Serves ``/status`` from ``self.body`` (bytes) with ``self.code``; other paths return 404."""

    def __init__(self) -> None:
        self.body: bytes = json.dumps(STATUS_FULL).encode()
        self.code = 200
        self.requests: list[tuple[str, str]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - http.server API
                outer.requests.append((self.path, self.headers.get("User-Agent", "")))
                if self.path != "/status":
                    self.send_error(404)
                    return
                self.send_response(outer.code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(outer.body)))
                self.end_headers()
                self.wfile.write(outer.body)

            def log_message(self, *_: object) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def set_status(self, data: dict) -> None:
        self.body = json.dumps(data).encode()

    @property
    def address(self) -> str:
        return f"ss14://127.0.0.1:{self.port}"

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def fake_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeStatusServer]:
    # urllib honours proxy environment variables; the cloud container sets them. Keep loopback direct.
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    server = FakeStatusServer()
    try:
        yield server
    finally:
        server.close()
