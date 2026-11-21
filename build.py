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


def tcl_tk_libraries() -> list[Path]:
    """Tcl/Tk shared libraries that PyInstaller's dependency scan cannot find by itself (Linux only).

    uv's Python for Linux links ``_tkinter`` against ``libtcl9.0.so`` and ``libtcl9tk9.0.so`` in the
    interpreter's own ``lib`` folder. Whether PyInstaller finds them depends on the Python patch release: in
    3.14.7 (which built 1.0.0) the extension has ``RPATH $ORIGIN/../..`` and ``ldd`` resolves them; in 3.14.6
    and 3.14.0 it has none, the interpreter finds them through its own RPATH, and ``ldd`` on the extension,
    which is what PyInstaller runs, reports "not found". PyInstaller then only logs "Library not found" and
    finishes: the Tcl scripts are in the bundle, the libraries are not, and the window dies on
    ``import tkinter``. Naming the files puts them next to the extension whichever Python built it; when
    PyInstaller finds them as well, the two entries collapse into one.
    """
    if not sys.platform.startswith("linux"):
        return []
    lib = Path(sys.base_prefix) / "lib"
    return sorted({p for pattern in ("libtcl*.so*", "libtk*.so*") for p in lib.glob(pattern) if p.is_file()})


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
    for library in tcl_tk_libraries():
        args += ["--add-binary", f"{library}{os.pathsep}."]
    for module in HIDDEN:
        args += ["--hidden-import", module]
    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    if "--cli" in sys.argv:
        build(SRC / "cli_main.py", "ss14-autojoin", console=True, description="SS14 Auto-Join command-line tool")
    else:
        build(SRC / "gui_main.py", "SS14AutoJoin", console=False, description="SS14 Auto-Join")
