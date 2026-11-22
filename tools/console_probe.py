"""Play the terminal for a windowed program, then report what the console shows. Windows only.

``python tools/console_probe.py OUT.json COMMAND [ARG ...]``, started with ``CREATE_NEW_CONSOLE``.

A windowed program typed into a terminal gets no standard handles and nobody waits for its output: to say
something it has to find the terminal's console itself. No pipe can observe whether it did. This script
plays the terminal instead: it owns a fresh console, starts the command with nothing redirected, waits for
it, and then reads the characters on its own console's screen. The result goes to a JSON file, because its
own output is the console under observation. ``tools/smoke_version.py`` and the tests use it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TIMEOUT = 180


def screen_text() -> str:
    """The text on this process's console, one line per screen row down to the cursor."""
    import ctypes
    from ctypes import wintypes

    class Coord(ctypes.Structure):
        _fields_ = [("x", ctypes.c_short), ("y", ctypes.c_short)]

    class SmallRect(ctypes.Structure):
        _fields_ = [(name, ctypes.c_short) for name in ("left", "top", "right", "bottom")]

    class ScreenBufferInfo(ctypes.Structure):
        _fields_ = [
            ("size", Coord),
            ("cursor", Coord),
            ("attributes", wintypes.WORD),
            ("window", SmallRect),
            ("maximum_window_size", Coord),
        ]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    k32.GetConsoleScreenBufferInfo.restype = wintypes.BOOL
    k32.GetConsoleScreenBufferInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ScreenBufferInfo)]
    k32.ReadConsoleOutputCharacterW.restype = wintypes.BOOL
    k32.ReadConsoleOutputCharacterW.argtypes = [
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        Coord,
        ctypes.POINTER(wintypes.DWORD),
    ]
    generic_read_write, share_read_write, open_existing = 0x80000000 | 0x40000000, 1 | 2, 3
    handle = k32.CreateFileW("CONOUT$", generic_read_write, share_read_write, None, open_existing, 0, None)
    if not handle or handle == ctypes.c_void_p(-1).value:
        raise OSError(f"cannot open CONOUT$ (error {ctypes.get_last_error()})")
    info = ScreenBufferInfo()
    if not k32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
        raise OSError(f"GetConsoleScreenBufferInfo failed (error {ctypes.get_last_error()})")
    lines = []
    for row in range(info.cursor.y + 1):
        buffer = ctypes.create_unicode_buffer(info.size.x + 1)
        count = wintypes.DWORD(0)
        if not k32.ReadConsoleOutputCharacterW(handle, buffer, info.size.x, Coord(0, row), ctypes.byref(count)):
            raise OSError(f"ReadConsoleOutputCharacterW failed (error {ctypes.get_last_error()})")
        lines.append(buffer[: count.value].rstrip())
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if sys.platform != "win32" or len(argv) < 2:
        print(__doc__)
        return 2
    out, command = Path(argv[0]), argv[1:]
    result: dict[str, object] = {"command": command}
    try:
        # Nothing is redirected, so no standard handles are passed on: what a shell does for a windowed program.
        result["returncode"] = subprocess.run(command, check=False, timeout=TIMEOUT).returncode
        result["screen"] = screen_text()
    except (OSError, subprocess.TimeoutExpired) as e:
        result["error"] = f"{type(e).__name__}: {e}"
    out.write_text(json.dumps(result), encoding="utf-8")
    return 1 if "error" in result else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
