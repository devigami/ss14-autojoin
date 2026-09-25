from __future__ import annotations

from pathlib import Path

import pytest

from ss14_autojoin import launcher as L


def make_install(root: Path, dotnet: str | None = "dotnet_x64", bin_dir: str = "bin_x64") -> Path:
    (root / bin_dir / "loader").mkdir(parents=True)
    (root / bin_dir / L.LAUNCHER_EXE).write_bytes(b"")
    (root / bin_dir / "loader" / L.LOADER_EXE).write_bytes(b"")
    (root / bin_dir / "signing_key").write_bytes(b"")
    if dotnet:
        (root / dotnet).mkdir()
        (root / dotnet / ("dotnet.exe" if L.LAUNCHER_EXE.endswith(".exe") else "dotnet")).write_bytes(b"")
    return root


def test_install_from_root_describes_layout(tmp_path: Path) -> None:
    root = make_install(tmp_path / "steamapps" / "common" / "Space Station 14 Playtest")
    install = L.install_from_root(root, "test")
    assert install is not None
    assert install.launcher_exe == root / "bin_x64" / L.LAUNCHER_EXE
    assert install.loader_exe == root / "bin_x64" / "loader" / L.LOADER_EXE
    assert install.dotnet_root == root / "dotnet_x64"
    assert install.flavour == "steam"
    assert install.source == "test"
    assert install.child_env == {"DOTNET_ROOT": str(root / "dotnet_x64")}


def test_install_from_root_accepts_bin_dir_or_exe(tmp_path: Path) -> None:
    root = make_install(tmp_path / "SS14.Launcher_Windows")
    assert L.install_from_root(root / "bin_x64").root == root
    assert L.install_from_root(root / "bin_x64" / L.LAUNCHER_EXE).root == root
    assert L.install_from_root(root).flavour == "standalone"


def test_install_from_root_rejects_other_folders(tmp_path: Path) -> None:
    assert L.install_from_root(tmp_path) is None
    (tmp_path / "bin_x64").mkdir()
    assert L.install_from_root(tmp_path) is None


@pytest.mark.parametrize("dotnet", ["dotnet_x86", "dotnet_arm64", "dotnet"])
def test_dotnet_root_variants(tmp_path: Path, dotnet: str) -> None:
    root = make_install(tmp_path / "L", dotnet=dotnet)
    assert L.find_dotnet_root(root) == root / dotnet


def test_dotnet_root_prefers_x64_and_needs_dotnet_binary(tmp_path: Path) -> None:
    root = make_install(tmp_path / "L", dotnet="dotnet_x86")
    (root / "dotnet_x64").mkdir()  # empty folder must not win
    assert L.find_dotnet_root(root) == root / "dotnet_x86"
    assert L.install_from_root(make_install(tmp_path / "M", dotnet=None)).dotnet_root is None
    assert L.install_from_root(make_install(tmp_path / "M2", dotnet=None)).child_env == {}


def test_steam_library_roots_reads_vdf(tmp_path: Path) -> None:
    steam = tmp_path / "Steam"
    (steam / "steamapps" / "common").mkdir(parents=True)
    other = tmp_path / "D" / "SteamLibrary"
    (other / "steamapps" / "common").mkdir(parents=True)
    missing = tmp_path / "gone"
    vdf = f'''"libraryfolders"
{{
    "0"
    {{
        "path"		"{steam}"
    }}
    "1"
    {{
        "path"		"{str(other).replace(chr(92), chr(92) * 2)}"
    }}
    "2"
    {{
        "path"		"{missing}"
    }}
}}
'''
    (steam / "steamapps" / "libraryfolders.vdf").write_text(vdf)
    assert list(L.steam_library_roots([steam])) == [steam / "steamapps" / "common", other / "steamapps" / "common"]


def test_root_from_launcher_log_uses_newest_launch_command(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "launcher-20260925.log").write_text(
        "2026-09-25 10:00:00.000 +10:00 [DBG] Launch command: C:\\old\\bin_x64\\loader\\SS14.Loader.exe [0] x\n"
    )
    (logs / "launcher-20260926.log").write_text(
        "2026-09-26 08:45:25.646 +10:00 [DBG] Launch command: D:\\SteamLibrary\\steamapps\\common\\Space Station 14 "
        "Playtest\\bin_x64\\loader\\SS14.Loader.exe [0] C:\\Users\\jacob\\AppData\\Roaming\\Space Station 14\\launcher"
        "\\engines\\290.0.0.zip [1] DA18 [2] D:\\x\\signing_key [3] --username [4] PLAYER\n"
        "2026-09-26 09:05:27.330 +10:00 [DBG] Launch command: D:\\SteamLibrary\\steamapps\\common\\Space Station 14 "
        "Playtest\\bin_x64\\loader\\SS14.Loader.exe [0] again\n"
    )
    root = L.root_from_launcher_log(logs)
    assert root is not None
    # Path arithmetic on a Windows-style string works on both platforms via PureWindowsPath-like parts.
    assert str(root).endswith("Space Station 14 Playtest")
    assert L.root_from_launcher_log(tmp_path / "nope") is None
    (logs / "launcher-20260927.log").write_text("nothing here\n")
    assert str(L.root_from_launcher_log(logs)).endswith("Space Station 14 Playtest")


def test_roots_from_processes(tmp_path: Path) -> None:
    exe = tmp_path / "Inst" / "bin_x64" / L.LAUNCHER_EXE
    roots = L.roots_from_processes(lambda: [str(exe), str(tmp_path / "other.exe"), str(exe)])
    assert roots == [tmp_path / "Inst"]


def test_candidate_order_and_find(tmp_path: Path) -> None:
    home = tmp_path / "home"
    env = {"LOCALAPPDATA": str(home / "AppData" / "Local"), "ProgramFiles(x86)": str(tmp_path / "PF86")}
    steam = tmp_path / "PF86" / "Steam"
    (steam / "steamapps" / "common").mkdir(parents=True)
    steam_install = make_install(steam / "steamapps" / "common" / "Space Station 14 Playtest")
    standalone = make_install(home / "Downloads" / "SS14.Launcher_Windows")
    configured = tmp_path / "configured-but-empty"

    roots = L.candidate_roots(configured, env, home, steam_dirs=[steam])
    assert roots[0] == (configured, "configured")
    assert (steam_install, "steam library") in roots
    assert (standalone, "common path") in roots
    assert roots.index((steam_install, "steam library")) < roots.index((standalone, "common path"))

    found = L.find_launcher(configured, env, home, steam_dirs=[steam])
    assert found is not None and found.root == steam_install and found.source == "steam library"

    found = L.find_launcher(standalone, env, home, steam_dirs=[steam])
    assert found is not None and found.root == standalone and found.source == "configured"

    running = lambda: [str(standalone / "bin_x64" / L.LAUNCHER_EXE)]  # noqa: E731
    found = L.find_launcher(None, env, home, process_exes=running, steam_dirs=[steam])
    assert found is not None and found.source == "running launcher"

    assert L.find_launcher(None, {}, tmp_path / "empty-home", steam_dirs=[]) is None


def test_launcher_data_dir(tmp_path: Path) -> None:
    home = tmp_path / "home"
    default = L.launcher_data_dir({}, home)
    assert default.name == "launcher" and default.parent.name == "Space Station 14"
    assert L.launcher_data_dir({"SS14_LAUNCHER_APPDATA_NAME": "launcherTest"}, home).name == "launcherTest"
    if L.LAUNCHER_EXE.endswith(".exe"):
        assert (
            L.launcher_data_dir({"APPDATA": str(tmp_path / "Roaming")}, home).parent
            == tmp_path / "Roaming" / "Space Station 14"
        )
    else:
        assert (
            L.launcher_data_dir({"XDG_DATA_HOME": str(tmp_path / "xdg")}, home).parent
            == tmp_path / "xdg" / "Space Station 14"
        )
