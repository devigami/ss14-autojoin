"""Print one line to the command line, including from the window executable.

The window executable is built without a console (PyInstaller ``--noconsole``), which makes it a Windows
GUI-subsystem program. Started from a terminal, such a program has no console of its own and Python's
``sys.stdout`` is ``None``: a plain ``print`` shows nothing. Three routes exist, tried in this order:

1. ``sys.stdout``, when Python has one: the console build, running from source, Linux and macOS, and output
   the caller captured in a way Python can see. The bytes go straight to the file descriptor, because a
   caller may have stopped listening (PowerShell does not wait for a windowed program in
   ``$v = SS14AutoJoin --version`` and closes its end of the pipe): text left in Python's buffer would then
   fail again when the interpreter exits, with an "Exception ignored while flushing sys.stdout" message.
2. The process's standard output handle, when the caller redirected it (a pipe or a file) but Python made
   no stream for it.
3. The console of the parent process, which is the terminal the command was typed in, attached for the
   occasion. The shell does not wait for a windowed program, so its prompt is already back by the time the
   text arrives; the text therefore starts on a fresh line.

Everything Windows-specific sits behind :class:`ConsoleApi`, so the choice between the routes is tested with
a fake. :class:`WindowsConsole` is the real one; what it does on a real machine is in the verification record.
"""

from __future__ import annotations

import os
import sys
from types import EllipsisType
from typing import Protocol, TextIO


class ConsoleApi(Protocol):
    def write_std_handle(self, data: bytes) -> bool:
        """Write to the process's standard output handle. False when there is none worth writing to."""

    def write_parent_console(self, text: str) -> bool:
        """Attach to the parent process's console and write there. False when there is no such console."""


def emit(
    text: str,
    *,
    stream: TextIO | None | EllipsisType = ...,
    platform: str = sys.platform,
    api: ConsoleApi | None = None,
) -> str:
    """Print ``text`` as one line wherever a command-line caller will see it.

    Returns the route that took it: ``"stdout"``, ``"handle"``, ``"console"``, or ``"none"`` when nobody is
    listening (started from a shortcut, say). ``stream`` defaults to ``sys.stdout`` as it is at call time.
    """
    out = sys.stdout if stream is ... else stream
    if out is not None and _write_stream(out, text):
        return "stdout"
    if platform != "win32":
        return "none"
    try:
        console = api if api is not None else WindowsConsole()
        if console.write_std_handle((text + "\r\n").encode("utf-8", "replace")):
            return "handle"
        if console.write_parent_console("\n" + text + "\n"):
            return "console"
    except OSError:
        pass
    return "none"


def _write_stream(out: TextIO, text: str) -> bool:
    """Write one line to a Python stream. False when it could not be delivered, with nothing left buffered."""
    try:
        fd = out.fileno()
    except AttributeError, OSError, ValueError:
        fd = None  # an in-memory stream, as in tests: no descriptor, and nothing that can break
    try:
        if fd is None:
            out.write(text + "\n")
            out.flush()
        else:
            out.flush()  # anything written earlier goes first
            os.write(fd, (text + os.linesep).encode("utf-8", "replace"))
    except OSError, ValueError:
        return False  # closed, or a pipe nobody reads any more: try the handles
    return True


class WindowsConsole:
    """The real :class:`ConsoleApi`, through kernel32. Construct it on Windows only."""

    STD_OUTPUT_HANDLE = 0xFFFFFFF5  # (DWORD)-11
    ATTACH_PARENT_PROCESS = 0xFFFFFFFF  # (DWORD)-1
    FILE_TYPE_UNKNOWN = 0
    ERROR_ACCESS_DENIED = 5

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._dword = wintypes.DWORD
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        k32.GetStdHandle.restype = wintypes.HANDLE
        k32.GetStdHandle.argtypes = [wintypes.DWORD]
        k32.GetFileType.restype = wintypes.DWORD
        k32.GetFileType.argtypes = [wintypes.HANDLE]
        k32.WriteFile.restype = wintypes.BOOL
        k32.WriteFile.argtypes = [
            wintypes.HANDLE,
            ctypes.c_char_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        k32.AttachConsole.restype = wintypes.BOOL
        k32.AttachConsole.argtypes = [wintypes.DWORD]
        self._k32 = k32

    def write_std_handle(self, data: bytes) -> bool:
        handle = self._k32.GetStdHandle(self.STD_OUTPUT_HANDLE)
        invalid = self._ctypes.c_void_p(-1).value
        if not handle or handle == invalid:
            return False  # a windowed program started from a terminal without redirection has none
        if self._k32.GetFileType(handle) == self.FILE_TYPE_UNKNOWN:
            return False  # a stale value inherited from the parent, not an open file, pipe or console
        written = self._dword(0)
        ok = self._k32.WriteFile(handle, data, len(data), self._ctypes.byref(written), None)
        return bool(ok) and written.value == len(data)

    def write_parent_console(self, text: str) -> bool:
        if not self._k32.AttachConsole(self.ATTACH_PARENT_PROCESS):
            # "Access denied" means this process already has a console, which CONOUT$ then opens just the
            # same; any other error means the parent has no console to attach to.
            if self._ctypes.get_last_error() != self.ERROR_ACCESS_DENIED:
                return False
        try:
            with open("CONOUT$", "w", encoding="utf-8") as console:
                console.write(text)
        except OSError:
            return False
        return True
