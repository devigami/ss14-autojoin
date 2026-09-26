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
        assert doc["PackageIdentifier"] == "Devigami.SS14AutoJoin" and doc["ManifestVersion"] == "1.10.0"


def test_checked_in_manifest_for_1_0_0_matches_the_generator() -> None:
    mod = load_module("make_winget_manifest", ROOT / "tools" / "make_winget_manifest.py")
    folder = ROOT / "packaging" / "winget" / "manifests" / "d" / "Devigami" / "SS14AutoJoin" / "1.0.0"
    installer = yaml.safe_load((folder / "Devigami.SS14AutoJoin.installer.yaml").read_text())
    sha = installer["Installers"][0]["InstallerSha256"]
    expected = mod.manifests("1.0.0", sha, installer["ReleaseDate"].isoformat())
    for name, text in expected.items():
        assert (folder / name).read_text() == text, name


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
