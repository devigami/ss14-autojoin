"""Build the one-file desktop executable with PyInstaller: ``uv run python build.py``.

Windows: ``dist/SS14AutoJoin.exe`` (no console window). Linux/macOS: ``dist/SS14AutoJoin`` (used to smoke-test the
frozen build in CI and the cloud). The entry script is ``gui_main.py``, which nothing imports; the CLI is a
separate console build when ``--cli`` is given (``dist/ss14-autojoin[.exe]``).
"""

from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src" / "ss14_autojoin"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
COMPANY = "SS14 Auto-Join contributors"
COPYRIGHT = "MIT licence. Not affiliated with Space Wizards Federation."


def version_tuple(version: str) -> tuple[int, int, int, int]:
    parts = [int(p) for p in version.split(".")[:4] if p.isdigit()]
    return tuple((parts + [0, 0, 0, 0])[:4])  # type: ignore[return-value]


def write_version_file(name: str, description: str, console: bool) -> Path:
    """A Windows VERSIONINFO resource for the executable (Explorer's Details tab, SmartScreen heuristics)."""
    major, minor, patch, build = version_tuple(VERSION)
    path = ROOT / "build" / f"version_{name}.txt"
    path.parent.mkdir(exist_ok=True)
    strings = {
        "CompanyName": COMPANY,
        "FileDescription": description,
        "FileVersion": VERSION,
        "InternalName": name,
        "LegalCopyright": COPYRIGHT,
        "OriginalFilename": f"{name}.exe",
        "ProductName": "SS14 Auto-Join",
        "ProductVersion": VERSION,
        "Comments": "https://github.com/devigami/ss14-autojoin",
    }
    table = ",\n".join(f"        StringStruct({k!r}, {v!r})" for k, v in strings.items())
    path.write_text(
        f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, {build}),
    prodvers=({major}, {minor}, {patch}, {build}),
    mask=0x3F,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
{table}
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
""",
        encoding="utf-8",
    )
    return path


HIDDEN = ["psutil", "tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox", "tkinter.scrolledtext"]


def build(entry: Path, name: str, console: bool, description: str) -> None:
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
        "--icon",
        str(SRC / "data" / "icon.ico"),
    ]
    if sys.platform == "win32":
        args += ["--version-file", str(write_version_file(name, description, console))]
    for module in HIDDEN:
        args += ["--hidden-import", module]
    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    if "--cli" in sys.argv:
        build(SRC / "cli_main.py", "ss14-autojoin", console=True, description="SS14 Auto-Join command-line tool")
    else:
        build(SRC / "gui_main.py", "SS14AutoJoin", console=False, description="SS14 Auto-Join")
