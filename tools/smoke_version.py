"""Run built executables with ``--version`` and check what comes back.

``uv run python tools/smoke_version.py dist/SS14AutoJoin.exe dist/ss14-autojoin.exe``

Each executable must exit 0 and print one line that ends in the version from ``pyproject.toml``. The window
executable has no console, so this is the check that its version still reaches a caller that captures the
output; it also proves that a freshly built one-file executable starts at all. CI runs it after every build
and the release workflow runs it before anything is published.

The window executable (file name starting with ``SS14AutoJoin``) gets two more runs. In one the caller stops
listening before the answer comes, as PowerShell does in ``$v = SS14AutoJoin --version``: it must still exit
0 and say nothing on the error stream. In the other, on Windows, it is started from a fresh console with
nothing redirected, as when the command is typed into a terminal (``tools/console_probe.py``): the version
must appear on that console.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = 180  # a one-file executable unpacks itself first; slow on a cold CI disk


def expected_version() -> str:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def check(exe: Path, version: str) -> str | None:
    """None when the executable answers correctly, otherwise what went wrong."""
    try:
        done = subprocess.run([str(exe), "--version"], capture_output=True, timeout=TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"could not run it: {e}"
    out = done.stdout.decode("utf-8", "replace")
    lines = out.split()
    print(f"{exe}: exit {done.returncode}, printed {out!r}")
    if done.returncode != 0:
        return f"exit code {done.returncode}; stderr: {done.stderr.decode('utf-8', 'replace')!r}"
    if len(out.strip().splitlines()) != 1 or not lines or lines[-1] != version:
        return f"expected one line ending in {version!r}"
    return None


def check_unheard(exe: Path) -> str | None:
    """Run ``--version`` with a pipe nobody reads. None when the executable takes that quietly."""
    try:
        child = subprocess.Popen([str(exe), "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as e:
        return f"could not run it: {e}"
    assert child.stdout is not None and child.stderr is not None
    child.stdout.close()  # long before a one-file executable has unpacked itself
    try:
        stderr = child.stderr.read().decode("utf-8", "replace")
        code = child.wait(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        child.kill()
        return "did not exit when nobody was listening"
    print(f"{exe}: nobody listening: exit {code}, error stream {stderr!r}")
    if code != 0 or stderr.strip():
        return f"nobody listening: exit code {code}, error stream {stderr!r}"
    return None


def check_typed_in_a_terminal(exe: Path, version: str) -> str | None:
    """Windows: run ``--version`` from a fresh console with nothing redirected. None when the version shows there."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "probe.json"
        subprocess.run(
            [sys.executable, str(ROOT / "tools" / "console_probe.py"), str(out), str(exe.resolve()), "--version"],
            creationflags=subprocess.CREATE_NEW_CONSOLE,  # type: ignore[attr-defined]
            timeout=TIMEOUT + 60,
            check=False,
        )
        if not out.exists():
            return "typed in a terminal: the console probe wrote no result"
        result = json.loads(out.read_text(encoding="utf-8"))
    print(f"{exe}: typed in a terminal: {result}")
    shown = [line.strip() for line in str(result.get("screen", "")).splitlines() if line.strip()]
    if "error" in result or result.get("returncode") != 0:
        return f"typed in a terminal: {result}"
    if len(shown) != 1 or shown[0].split()[-1] != version:
        return f"typed in a terminal: expected one line ending in {version!r} on the console, saw {shown!r}"
    return None


def is_window_build(exe: Path) -> bool:
    return exe.name.startswith("SS14AutoJoin")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    version = expected_version()
    failures = [f"{exe}: {problem}" for exe in map(Path, argv) if (problem := check(exe, version))]
    windows = [exe for exe in map(Path, argv) if is_window_build(exe)]
    failures += [f"{exe}: {p}" for exe in windows if (p := check_unheard(exe))]
    if sys.platform == "win32":
        failures += [f"{exe}: {p}" for exe in windows if (p := check_typed_in_a_terminal(exe, version))]
    for failure in failures:
        print(f"FAILED {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
