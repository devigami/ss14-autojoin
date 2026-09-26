"""Build the one-file desktop executable with PyInstaller: ``uv run python build.py``.

Windows: ``dist/SS14AutoJoin.exe`` (no console window). Linux/macOS: ``dist/SS14AutoJoin`` (used to smoke-test the
frozen build in CI and the cloud). The entry script is ``gui_main.py``, which nothing imports; the CLI is a
separate console build when ``--cli`` is given (``dist/ss14-autojoin[.exe]``).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src" / "ss14_autojoin"

HIDDEN = ["psutil", "tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox", "tkinter.scrolledtext"]


def build(entry: Path, name: str, console: bool) -> None:
    args = [
        str(entry),
        "--onefile",
        "--name",
        name,
        "--paths",
        str(ROOT / "src"),
        "--clean",
        "--noconfirm",
        "--console" if console else "--noconsole",
        "--add-data",
        f"{SRC / 'data'}{os.pathsep}ss14_autojoin/data",
    ]
    for module in HIDDEN:
        args += ["--hidden-import", module]
    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    if "--cli" in sys.argv:
        build(SRC / "cli_main.py", "ss14-autojoin", console=True)
    else:
        build(SRC / "gui_main.py", "SS14AutoJoin", console=False)
