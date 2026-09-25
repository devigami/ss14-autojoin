"""The real :class:`~ss14_autojoin.joiner.Ports`: launcher process, log files, game client process.

This is the only module that starts or stops processes. Tested on Jacob's machine through the hand-off; here
only its pure parts are unit-tested.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from .client import LauncherEvent, LauncherLogTail, LogTail
from .launcher import LAUNCHER_EXE, LOADER_EXE, LauncherInstall, launcher_data_dir
from .server import ServerAddress, ServerStatus, fetch_status

log = logging.getLogger(__name__)


def launcher_command(install: LauncherInstall, uri: str) -> tuple[list[str], dict[str, str]]:
    """The command and environment that make the launcher connect: ``bin_x64\\SS14.Launcher.exe <uri>``."""
    env = dict(os.environ)
    env.update(install.child_env)
    return [str(install.launcher_exe), uri], env


class RealPorts:
    def __init__(self, install: LauncherInstall, data_dir: Path | None = None, status_timeout: float = 5.0) -> None:
        self.install = install
        self.data_dir = data_dir or launcher_data_dir()
        self.status_timeout = status_timeout
        logs = self.data_dir / "logs"
        self._launcher_tail = LauncherLogTail(logs, start_at_end=True)
        self._client_tail = LogTail(logs / "client.stdout.log", start_at_end=True)
        self._children: list[subprocess.Popen[bytes]] = []

    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def fetch_status(self, address: ServerAddress) -> ServerStatus:
        return fetch_status(address, timeout=self.status_timeout)

    def send_connect(self, uri: str) -> None:
        argv, env = launcher_command(self.install, uri)
        log.info("running %s", " ".join(argv))
        kwargs: dict = {"env": env, "cwd": str(self.install.launcher_exe.parent)}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
        # When a launcher is running this process forwards the URI and exits; otherwise it *is* the launcher.
        # Either way we never wait for it.
        self._children.append(
            subprocess.Popen(
                argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs
            )
        )
        self._children = [c for c in self._children if c.poll() is None]

    def launcher_events(self) -> list[LauncherEvent]:
        return self._launcher_tail.read_new()

    def client_lines(self) -> list[str]:
        return self._client_tail.read_new()

    def reset_client_log(self) -> None:
        # The launcher recreates client.stdout.log at the next client start; until then the old file is
        # there. Start at its end so the previous attempt's lines are not read as this one's; the tail
        # detects the recreation (size drop / new identity) and restarts from 0.
        self._client_tail = LogTail(self._client_tail.path, start_at_end=True)

    def process_alive(self, pid: int) -> bool:
        import psutil  # noqa: PLC0415

        try:
            proc = psutil.Process(pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except psutil.Error:
            return False

    def terminate(self, pid: int) -> None:
        import psutil  # noqa: PLC0415

        try:
            proc = psutil.Process(pid)
        except psutil.Error:
            return
        if proc.name().lower() not in (LOADER_EXE.lower(), "robust.client", "robust.client.exe"):
            log.warning("pid %s is %s, not the game client; not touching it", pid, proc.name())
            return
        log.info("terminating game client pid %s (%s)", pid, proc.name())
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except psutil.TimeoutExpired:
            log.warning("client did not exit after terminate; killing")
            proc.kill()
        except psutil.Error:
            pass

    def restart_launcher(self, uri: str) -> None:
        import psutil  # noqa: PLC0415

        for proc in psutil.process_iter(["name"]):
            if (proc.info.get("name") or "").lower() == LAUNCHER_EXE.lower():
                log.info("terminating launcher pid %s", proc.pid)
                try:
                    proc.terminate()
                    proc.wait(timeout=10)
                except psutil.TimeoutExpired:
                    proc.kill()
                except psutil.Error:
                    pass
        time.sleep(1.0)
        self.send_connect(uri)
