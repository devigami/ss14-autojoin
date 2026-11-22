from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ss14_autojoin import __version__, app
from ss14_autojoin.console import MAX_ANCESTORS, attach_nearest_console, emit

PROBE = Path(__file__).resolve().parent.parent / "tools" / "console_probe.py"


class FakeConsole:
    """Stands in for kernel32: records what each route was given and answers as scripted."""

    def __init__(self, handle: bool = False, parent: bool = False) -> None:
        self.handle, self.parent = handle, parent
        self.handle_data: list[bytes] = []
        self.parent_text: list[str] = []

    def write_std_handle(self, data: bytes) -> bool:
        self.handle_data.append(data)
        return self.handle

    def write_parent_console(self, text: str) -> bool:
        self.parent_text.append(text)
        return self.parent


class BrokenStream(io.StringIO):
    def write(self, s: str) -> int:
        raise OSError("the pipe is gone")


def test_a_python_stream_is_used_when_there_is_one() -> None:
    out, api = io.StringIO(), FakeConsole(handle=True, parent=True)
    assert emit("SS14 Auto-Join 9.9.9", stream=out, platform="win32", api=api) == "stdout"
    assert out.getvalue() == "SS14 Auto-Join 9.9.9\n"
    assert api.handle_data == [] and api.parent_text == []  # nothing is printed twice


def test_windowed_build_with_redirected_output_writes_to_the_handle() -> None:
    api = FakeConsole(handle=True, parent=True)
    assert emit("SS14 Auto-Join 9.9.9", stream=None, platform="win32", api=api) == "handle"
    assert api.handle_data == [b"SS14 Auto-Join 9.9.9\r\n"]
    assert api.parent_text == []


def test_windowed_build_typed_in_a_terminal_writes_to_the_parent_console_on_a_fresh_line() -> None:
    api = FakeConsole(handle=False, parent=True)
    assert emit("SS14 Auto-Join 9.9.9", stream=None, platform="win32", api=api) == "console"
    # the shell's prompt is already back, so the text must not continue that line
    assert api.parent_text == ["\nSS14 Auto-Join 9.9.9\n"]


def test_the_console_is_looked_for_up_the_process_tree_nearest_first() -> None:
    tried: list[int] = []

    def attach(pid: int, having_console: frozenset[int] = frozenset({30, 40})) -> bool:
        tried.append(pid)
        return pid in having_console

    # 10 is the bootloader of the one-file build, 20 a launcher: neither has a console; 30 is the terminal.
    assert attach_nearest_console(attach, [10, 20, 30, 40]) is True
    assert tried == [10, 20, 30]  # stops at the nearest one, never reaches 40
    tried.clear()
    assert attach_nearest_console(attach, [10, 20, 30], limit=1) is False  # parent only: what 1.0.1 first did
    assert tried == [10]
    assert attach_nearest_console(attach, []) is False  # no ancestors at all
    assert attach_nearest_console(attach, iter(range(100, 200))) is False  # started from a shortcut
    assert len(tried) == 1 + MAX_ANCESTORS  # and the search is bounded


def test_nobody_listening_is_not_an_error() -> None:
    assert emit("x", stream=None, platform="win32", api=FakeConsole()) == "none"  # started from a shortcut
    assert emit("x", stream=None, platform="linux") == "none"  # no Windows calls off Windows


def test_a_broken_stream_falls_through_to_the_handles() -> None:
    api = FakeConsole(handle=True)
    assert emit("x", stream=BrokenStream(), platform="win32", api=api) == "handle"
    assert emit("x", stream=BrokenStream(), platform="linux") == "none"


def test_a_real_descriptor_gets_the_line_directly() -> None:
    read_fd, write_fd = os.pipe()
    with os.fdopen(write_fd, "w") as out, os.fdopen(read_fd, "rb") as back:
        assert emit("SS14 Auto-Join 9.9.9", stream=out, platform="linux") == "stdout"
        assert os.read(back.fileno(), 100) == ("SS14 Auto-Join 9.9.9" + os.linesep).encode()


def test_a_pipe_nobody_reads_leaves_nothing_buffered() -> None:
    read_fd, write_fd = os.pipe()
    os.close(read_fd)  # the caller stopped listening before the answer came
    out = os.fdopen(write_fd, "w")
    api = FakeConsole(parent=True)
    assert emit("SS14 Auto-Join 9.9.9", stream=out, platform="win32", api=api) == "console"
    out.close()  # would raise if the line were still sitting in the buffer


def test_window_version_is_silent_and_successful_when_the_caller_stops_listening() -> None:
    """Real processes on every platform: the answer is lost, which must not become an error or a message."""
    code = "import sys; sys.stdin.readline(); from ss14_autojoin.app import main; raise SystemExit(main(['--version']))"
    child = subprocess.Popen(
        [sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    assert child.stdin is not None and child.stdout is not None and child.stderr is not None
    child.stdout.close()  # stop listening, then let the child go ahead
    child.stdin.write(b"\n")
    child.stdin.close()
    stderr = child.stderr.read()
    child.stderr.close()
    assert child.wait(timeout=60) == 0, stderr
    assert b"Exception" not in stderr and b"Error" not in stderr, stderr


def test_window_version_flag_prints_and_never_opens_a_window(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_window(*a: object, **k: object) -> None:
        raise AssertionError("--version must not create a window")

    monkeypatch.setattr(app.tk, "Tk", no_window)
    monkeypatch.setattr(app, "load", no_window)  # nor read the settings file
    for flag in ("--version", "-V"):
        assert app.main([flag]) == 0
        assert capsys.readouterr().out == f"SS14 Auto-Join {__version__}\n"
    assert app.version_line() == f"SS14 Auto-Join {__version__}"  # also the title bar


def test_cli_gui_command_does_not_pass_its_own_arguments_to_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    from ss14_autojoin import cli

    seen: list[object] = []
    monkeypatch.setattr(app, "main", lambda argv=None: seen.append(argv) or 0)
    monkeypatch.setattr(sys, "argv", ["ss14-autojoin", "gui"])
    assert cli.main(["gui"]) == 0
    assert seen == [[]]


# The two tests below run the real kernel32 calls, so they only exist on Windows (CI has a Windows runner).
# They cover the redirected-output route. Typing the command in a terminal (the parent-console route) cannot
# be observed from a test and is checked by hand; see docs/development/verification.md.
windows_only = pytest.mark.skipif(sys.platform != "win32", reason="real Windows console API")


@windows_only
def test_real_std_handle_route_reaches_a_pipe() -> None:
    code = (
        "import sys; from ss14_autojoin.console import WindowsConsole; "
        "sys.exit(0 if WindowsConsole().write_std_handle(b'through the handle\\r\\n') else 3)"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    assert done.stdout == b"through the handle\r\n"


@windows_only
def test_real_emit_without_a_python_stream_reaches_a_pipe() -> None:
    # What the window executable looks like to Python: no sys.stdout, yet the caller is capturing the output.
    code = (
        "import sys; sys.stdout = None; from ss14_autojoin.console import emit; "
        "route = emit('SS14 Auto-Join 9.9.9'); sys.exit(0 if route == 'handle' else 4)"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    assert done.stdout == b"SS14 Auto-Join 9.9.9\r\n"


# The tests below observe a real console. tools/console_probe.py plays the terminal: it owns a fresh console,
# runs a command with nothing redirected, and reports what ended up on its screen.


def run_in_fresh_console(tmp_path: Path, command: list[str]) -> dict:
    out = tmp_path / "probe.json"
    subprocess.run(
        [sys.executable, str(PROBE), str(out), *command],
        creationflags=subprocess.CREATE_NEW_CONSOLE,  # type: ignore[attr-defined]
        timeout=300,
        check=False,
    )
    assert out.exists(), "the console probe wrote no result"
    result = json.loads(out.read_text(encoding="utf-8"))
    assert "error" not in result, result
    return result


def two_windowed_levels_down(code: str) -> list[str]:
    """Run ``code`` in a windowed Python whose parent is another windowed Python.

    That is the shape of the one-file build: the program's parent is its bootloader, which has no console,
    and the terminal sits further up.
    """
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    assert pythonw.exists(), f"no windowed interpreter next to {sys.executable}"
    outer = f"import subprocess, sys; raise SystemExit(subprocess.run([sys.executable, '-c', {code!r}]).returncode)"
    return [str(pythonw), "-c", outer]


@windows_only
def test_real_console_is_found_past_a_parent_that_has_none(tmp_path: Path) -> None:
    code = "from ss14_autojoin.app import main; raise SystemExit(main(['--version']))"
    result = run_in_fresh_console(tmp_path, two_windowed_levels_down(code))
    assert result["returncode"] == 0, result
    shown = [line for line in result["screen"].splitlines() if line.strip()]
    assert shown == [f"SS14 Auto-Join {__version__}"], result


@windows_only
def test_real_console_is_missed_when_only_the_parent_is_asked(tmp_path: Path) -> None:
    # The control for the test above, and the defect the reference machine showed: with the search limited
    # to the parent, a program two levels down prints nothing, and that is not an error.
    code = (
        "import sys; from ss14_autojoin.console import WindowsConsole, emit; "
        "route = emit('SS14 Auto-Join 0.0.0', api=WindowsConsole(max_ancestors=1)); "
        "sys.exit(0 if route == 'none' else 9)"
    )
    result = run_in_fresh_console(tmp_path, two_windowed_levels_down(code))
    assert result["returncode"] == 0, result
    assert "SS14" not in result["screen"], result
