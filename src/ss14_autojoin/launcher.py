"""Find the launcher installation and describe it.

Everything that touches the machine (environment, file system, registry, processes) is injected so the
discovery order can be tested on Linux with fake trees. The order, and why, is in ``docs/plan.md``
("Finding the launcher"); the facts about the layout are in ``docs/ss14-launcher-reference.md`` sections 11
and 11a.
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

LAUNCHER_EXE = "SS14.Launcher.exe" if sys.platform == "win32" else "SS14.Launcher"
LOADER_EXE = "SS14.Loader.exe" if sys.platform == "win32" else "SS14.Loader"
BIN_DIRS = ("bin_x64", "bin_arm64", "bin")
"""Where the launcher binary lives: ``bin_x64`` on Windows (publish.py), ``bin`` in the Linux tarball."""

STEAM_APP_DIRS = ("Space Station 14 Playtest", "Space Station 14")
"""Folder names under ``steamapps/common`` (Jacob's install is the Playtest one)."""

STANDALONE_DIR_NAMES = ("Space Station 14 Launcher", "SS14.Launcher_Windows", "SS14.Launcher", "SS14 Launcher")

_LAUNCH_COMMAND = re.compile(r"Launch command: (?P<loader>.+?[\\/]loader[\\/]SS14\.Loader(?:\.exe)?) \[0\]")
_VDF_PATH = re.compile(r'"path"\s+"(?P<path>[^"]+)"')


@dataclass(frozen=True, slots=True)
class LauncherInstall:
    """A launcher installation the tool can drive."""

    root: Path
    launcher_exe: Path
    loader_exe: Path | None
    dotnet_root: Path | None
    source: str
    flavour: str

    @property
    def child_env(self) -> dict[str, str]:
        """Extra environment for starting ``launcher_exe`` directly, mirroring the Windows bootstrap."""
        return {"DOTNET_ROOT": str(self.dotnet_root)} if self.dotnet_root else {}


def install_from_root(root: Path, source: str = "configured") -> LauncherInstall | None:
    """Describe the installation at ``root`` (the folder that holds ``bin_x64``), or None if none is there."""
    root = Path(root)
    for bin_dir in BIN_DIRS:
        launcher_exe = root / bin_dir / LAUNCHER_EXE
        if launcher_exe.is_file():
            break
    else:
        # Accept being pointed at bin_x64 itself, or at the executable.
        if root.name in BIN_DIRS and (root / LAUNCHER_EXE).is_file():
            return install_from_root(root.parent, source)
        if root.name == LAUNCHER_EXE and root.is_file():
            return install_from_root(root.parent.parent, source)
        return None
    loader = launcher_exe.parent / "loader" / LOADER_EXE
    flavour = "steam" if "steamapps" in {p.lower() for p in root.parts} else "standalone"
    return LauncherInstall(
        root=root,
        launcher_exe=launcher_exe,
        loader_exe=loader if loader.is_file() else None,
        dotnet_root=find_dotnet_root(root),
        source=source,
        flavour=flavour,
    )


def find_dotnet_root(root: Path) -> Path | None:
    """The bundled runtime folder (``dotnet_x64`` normally; any ``dotnet_*`` holding ``dotnet.exe`` or ``dotnet``)."""
    preferred = [root / "dotnet_x64", root / "dotnet_arm64", root / "dotnet_x86", root / "dotnet"]
    others = sorted(p for p in root.glob("dotnet*") if p.is_dir() and p not in preferred)
    for candidate in preferred + others:
        if candidate.is_dir() and any((candidate / name).is_file() for name in ("dotnet.exe", "dotnet")):
            return candidate
    return None


def steam_library_roots(steam_dirs: Iterable[Path]) -> Iterator[Path]:
    """Every Steam library's ``steamapps/common`` folder, read from ``libraryfolders.vdf`` of each Steam install."""
    seen: set[Path] = set()
    for steam in steam_dirs:
        libraries = [steam]
        vdf = steam / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            try:
                text = vdf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            libraries += [Path(m.group("path").replace("\\\\", "\\")) for m in _VDF_PATH.finditer(text)]
        for library in libraries:
            common = library / "steamapps" / "common"
            if common not in seen and common.is_dir():
                seen.add(common)
                yield common


def default_steam_dirs(env: Mapping[str, str], home: Path) -> list[Path]:
    """Where Steam itself is usually installed; the registry value comes first when available."""
    dirs: list[Path] = []
    registry = _steam_path_from_registry()
    if registry:
        dirs.append(registry)
    for var in ("ProgramFiles(x86)", "ProgramFiles"):
        if env.get(var):
            dirs.append(Path(env[var]) / "Steam")
    dirs += [Path(r"C:\Program Files (x86)\Steam"), Path(r"C:\Program Files\Steam")]
    dirs += [home / ".steam" / "steam", home / ".local" / "share" / "Steam"]  # Linux, for completeness
    return _unique(dirs)


def _steam_path_from_registry() -> Path | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg  # noqa: PLC0415 - Windows only

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            value, _ = winreg.QueryValueEx(key, "SteamPath")
        return Path(str(value))
    except OSError:
        return None


def standalone_candidates(env: Mapping[str, str], home: Path) -> list[Path]:
    """Places people extract the standalone launcher zip."""
    bases: list[Path] = []
    for var in ("LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)"):
        if env.get(var):
            bases.append(Path(env[var]))
    if env.get("LOCALAPPDATA"):
        bases.append(Path(env["LOCALAPPDATA"]) / "Programs")
    bases += [home / "Downloads", home / "Desktop", home / "Documents", home / "Games", home]
    bases += [Path(f"{drive}:\\Games") for drive in "CDEF"] + [Path(f"{drive}:\\") for drive in "CDEF"]
    return _unique([base / name for base in bases for name in STANDALONE_DIR_NAMES])


def root_from_launcher_log(log_dir: Path) -> Path | None:
    """The install root recorded in the newest launcher log's ``Launch command:`` line, if any."""
    logs = sorted(log_dir.glob("launcher-*.log"), reverse=True) if log_dir.is_dir() else []
    for log in logs[:7]:
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        matches = list(_LAUNCH_COMMAND.finditer(text))
        if matches:
            return _install_root_of_loader(matches[-1].group("loader"))
    return None


def _install_root_of_loader(loader_text: str) -> Path:
    """``<root>/bin_x64/loader/SS14.Loader.exe`` -> ``<root>``, for a path written by either OS."""
    windows_style = "\\" in loader_text or re.match(r"^[A-Za-z]:", loader_text) is not None
    pure = PureWindowsPath(loader_text) if windows_style else PurePosixPath(loader_text)
    return Path(str(pure.parent.parent.parent))


def roots_from_processes(process_exes: Callable[[], Iterable[str]]) -> list[Path]:
    """Install roots of running launcher processes (``exe`` paths supplied by the caller, usually psutil)."""
    roots = []
    for exe in process_exes():
        path = Path(exe)
        if path.name.lower() == LAUNCHER_EXE.lower():
            roots.append(path.parent.parent)
    return _unique(roots)


def candidate_roots(
    configured: Path | None,
    env: Mapping[str, str],
    home: Path,
    launcher_log_dir: Path | None = None,
    process_exes: Callable[[], Iterable[str]] | None = None,
    steam_dirs: Iterable[Path] | None = None,
) -> list[tuple[Path, str]]:
    """Install roots to try, in priority order, each with the name of the source that suggested it."""
    out: list[tuple[Path, str]] = []
    if configured:
        out.append((Path(configured), "configured"))
    if process_exes:
        out += [(r, "running launcher") for r in roots_from_processes(process_exes)]
    if launcher_log_dir:
        logged = root_from_launcher_log(launcher_log_dir)
        if logged:
            out.append((logged, "launcher log"))
    steam = steam_dirs if steam_dirs is not None else default_steam_dirs(env, home)
    for common in steam_library_roots(steam):
        out += [(common / app, "steam library") for app in STEAM_APP_DIRS]
    out += [(p, "common path") for p in standalone_candidates(env, home)]
    seen: set[Path] = set()
    unique: list[tuple[Path, str]] = []
    for root, source in out:
        if root not in seen:
            seen.add(root)
            unique.append((root, source))
    return unique


def find_launcher(
    configured: Path | None = None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
    launcher_log_dir: Path | None = None,
    process_exes: Callable[[], Iterable[str]] | None = None,
    steam_dirs: Iterable[Path] | None = None,
) -> LauncherInstall | None:
    """First installation found in :func:`candidate_roots` order; None when nothing is there."""
    env = os.environ if env is None else env
    home = Path.home() if home is None else home
    for root, source in candidate_roots(configured, env, home, launcher_log_dir, process_exes, steam_dirs):
        install = install_from_root(root, source)
        if install:
            return install
    return None


def launcher_data_dir(env: Mapping[str, str] | None = None, home: Path | None = None) -> Path:
    """The launcher's user data folder (logs, engines): ``%APPDATA%\\Space Station 14\\launcher`` on Windows."""
    env = os.environ if env is None else env
    home = Path.home() if home is None else home
    name = env.get("SS14_LAUNCHER_APPDATA_NAME") or "launcher"
    if sys.platform == "win32" and env.get("APPDATA"):
        base = Path(env["APPDATA"])
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        base = Path(env["XDG_DATA_HOME"]) if env.get("XDG_DATA_HOME") else home / ".local" / "share"
    return base / "Space Station 14" / name


def running_launcher_exes() -> list[str]:
    """Executable paths of running launcher processes, via psutil (empty when psutil is missing or denied)."""
    try:
        import psutil  # noqa: PLC0415 - optional at import time
    except ImportError:
        return []
    exes = []
    for proc in psutil.process_iter(["name", "exe"]):
        name = (proc.info.get("name") or "").lower()
        if name == LAUNCHER_EXE.lower() and proc.info.get("exe"):
            exes.append(proc.info["exe"])
    return exes


def _unique(paths: Iterable[Path]) -> list[Path]:
    seen: set[Path] = set()
    out = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out
