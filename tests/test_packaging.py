from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_winget_manifests_are_valid_yaml_with_the_right_fields() -> None:
    mod = load_module("make_winget_manifest", ROOT / "tools" / "make_winget_manifest.py")
    files = mod.manifests("1.2.3", "ab" * 32, "2026-09-26")
    assert set(files) == {
        "Devigami.SS14AutoJoin.yaml",
        "Devigami.SS14AutoJoin.installer.yaml",
        "Devigami.SS14AutoJoin.locale.en-US.yaml",
    }
    parsed = {name: yaml.safe_load(text) for name, text in files.items()}
    version = parsed["Devigami.SS14AutoJoin.yaml"]
    assert version["ManifestType"] == "version" and version["PackageVersion"] == "1.2.3"
    installer = parsed["Devigami.SS14AutoJoin.installer.yaml"]
    assert installer["InstallerType"] == "portable"
    (entry,) = installer["Installers"]
    assert entry["InstallerSha256"] == "AB" * 32
    assert entry["InstallerUrl"].endswith("/releases/download/v1.2.3/SS14AutoJoin-1.2.3-windows-x64.exe")
    assert entry["Commands"] == ["SS14AutoJoin"]  # the alias winget creates for a bare portable exe
    assert "PortableCommandAlias" not in entry  # that field only applies inside archives
    locale = parsed["Devigami.SS14AutoJoin.locale.en-US.yaml"]
    assert locale["ManifestType"] == "defaultLocale" and locale["License"] == "MIT"
    assert len(locale["ShortDescription"]) <= 256
    for doc in parsed.values():
        assert doc["PackageIdentifier"] == "Devigami.SS14AutoJoin" and doc["ManifestVersion"] == mod.SCHEMA
    # winget-pkgs rejected 1.10.0 as deprecated in 2026-10 (PR microsoft/winget-pkgs#441430); never go back.
    assert tuple(int(n) for n in mod.SCHEMA.split(".")) >= (1, 28, 0)
    for text in files.values():
        header = text.splitlines()[0]
        assert header.startswith("# yaml-language-server: $schema=https://aka.ms/winget-manifest.")
        assert header.endswith(f".{mod.SCHEMA}.schema.json")


def test_checked_in_manifest_for_1_0_0_matches_the_generator() -> None:
    mod = load_module("make_winget_manifest", ROOT / "tools" / "make_winget_manifest.py")
    folder = ROOT / "packaging" / "winget" / "manifests" / "d" / "Devigami" / "SS14AutoJoin" / "1.0.0"
    installer = yaml.safe_load((folder / "Devigami.SS14AutoJoin.installer.yaml").read_text())
    sha = installer["Installers"][0]["InstallerSha256"]
    expected = mod.manifests("1.0.0", sha, installer["ReleaseDate"].isoformat())
    for name, text in expected.items():
        assert (folder / name).read_text() == text, name


def test_the_version_is_the_same_everywhere() -> None:
    """pyproject.toml drives the release, __init__ is what --version prints, uv.lock is committed: keep them in step."""
    import tomllib

    from ss14_autojoin import __version__

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    (locked,) = [p["version"] for p in lock["package"] if p["name"] == "ss14-autojoin"]
    assert __version__ == project == locked


def test_smoke_version_accepts_only_one_line_ending_in_the_version(tmp_path: Path) -> None:
    smoke = load_module("smoke_version", ROOT / "tools" / "smoke_version.py")
    script = tmp_path / "fake_exe.py"

    def run(body: str) -> str | None:
        script.write_text(body, encoding="utf-8")
        launcher = tmp_path / ("fake.cmd" if sys.platform == "win32" else "fake.sh")
        if sys.platform == "win32":
            launcher.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
        else:
            launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
            launcher.chmod(0o755)
        return smoke.check(launcher, "1.2.3")

    assert run("print('SS14 Auto-Join 1.2.3')") is None
    assert run("print('ss14-autojoin 1.2.3')") is None
    assert "expected one line" in run("print('SS14 Auto-Join 1.2.4')")
    assert "expected one line" in run("pass")  # a windowed build that printed nothing
    assert "expected one line" in run("print('warning'); print('x 1.2.3')")
    assert "exit code 3" in run("import sys; print('x 1.2.3'); sys.exit(3)")
    assert smoke.expected_version() == load_module("build", ROOT / "build.py").VERSION


def test_build_names_the_tcl_tk_libraries_only_on_linux(tmp_path: Path, monkeypatch) -> None:
    build = load_module("build", ROOT / "build.py")
    lib = tmp_path / "lib"
    lib.mkdir()
    for name in ("libtcl9.0.so", "libtcl9tk9.0.so", "libpython3.14.so.1.0", "libtcl-notes.txt"):
        (lib / name).write_bytes(b"")
    (lib / "itcl4.3.5").mkdir()  # extension packages live in folders and are not needed by tkinter
    monkeypatch.setattr(build.sys, "base_prefix", str(tmp_path))
    monkeypatch.setattr(build.sys, "platform", "linux")
    assert [p.name for p in build.tcl_tk_libraries()] == ["libtcl9.0.so", "libtcl9tk9.0.so"]
    monkeypatch.setattr(build.sys, "platform", "win32")
    assert build.tcl_tk_libraries() == []  # PyInstaller finds the DLLs itself on Windows
    monkeypatch.setattr(build.sys, "platform", "linux")
    monkeypatch.setattr(build.sys, "base_prefix", str(tmp_path / "statically-linked-python"))
    assert build.tcl_tk_libraries() == []  # nothing to add, nothing to break


def test_build_version_tuple_and_version_file() -> None:
    sys.path.insert(0, str(ROOT))
    build = load_module("build", ROOT / "build.py")
    assert build.version_tuple("1.0.0") == (1, 0, 0, 0)
    assert build.version_tuple("1.2.3.4") == (1, 2, 3, 4)
    assert build.version_tuple("2.0.0rc1") == (2, 0, 0, 0)
    path = build.write_version_file("SS14AutoJoin", "SS14 Auto-Join", console=False)
    text = path.read_text(encoding="utf-8")

    class Node:  # PyInstaller evaluates the file with these names bound; mirror that to check the structure
        def __init__(self, *a, **k):
            self.a, self.k = a, k

    names = dict.fromkeys(
        ["VSVersionInfo", "FixedFileInfo", "StringFileInfo", "StringTable", "StringStruct", "VarFileInfo", "VarStruct"],
        Node,
    )
    info = eval(text, names)  # noqa: S307 - our own generated file
    assert info.k["ffi"].k["filevers"] == build.version_tuple(build.VERSION)
    strings = {s.a[0]: s.a[1] for s in info.k["kids"][0].a[0][0].a[1]}
    assert strings["ProductName"] == "SS14 Auto-Join" and strings["FileVersion"] == build.VERSION
    assert strings["OriginalFilename"] == "SS14AutoJoin.exe"
