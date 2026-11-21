"""Run built executables with ``--version`` and check what comes back.

``uv run python tools/smoke_version.py dist/SS14AutoJoin.exe dist/ss14-autojoin.exe``

Each executable must exit 0 and print one line that ends in the version from ``pyproject.toml``. The window
executable has no console, so this is the check that its version still reaches a caller that captures the
output; it also proves that a freshly built one-file executable starts at all. CI runs it after every build
and the release workflow runs it before anything is published.

The window executable (file name starting with ``SS14AutoJoin``) gets a second run in which the caller stops
listening before the answer comes, as PowerShell does in ``$v = SS14AutoJoin --version``. It must still exit
0 and say nothing on the error stream.
"""

from __future__ import annotations

import subprocess
import sys
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


def is_window_build(exe: Path) -> bool:
    return exe.name.startswith("SS14AutoJoin")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    version = expected_version()
    failures = [f"{exe}: {problem}" for exe in map(Path, argv) if (problem := check(exe, version))]
    failures += [f"{exe}: {p}" for exe in map(Path, argv) if is_window_build(exe) and (p := check_unheard(exe))]
    for failure in failures:
        print(f"FAILED {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
