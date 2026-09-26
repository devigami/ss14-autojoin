"""Write the winget manifests for a release: ``uv run python tools/make_winget_manifest.py 1.0.0 <sha256>``.

The three files land in ``packaging/winget/manifests/d/Devigami/SS14AutoJoin/<version>/`` in the layout the
``microsoft/winget-pkgs`` repository expects, ready to copy into a fork and open as a pull request. The SHA-256
is that of ``SS14AutoJoin-<version>-windows-x64.exe`` from the GitHub release (see ``SHA256SUMS.txt``).
Once the package exists in winget, ``release.yml`` submits later versions automatically.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

IDENTIFIER = "Devigami.SS14AutoJoin"
SCHEMA = "1.10.0"
REPO = "https://github.com/devigami/ss14-autojoin"
ROOT = Path(__file__).resolve().parents[1]


def manifests(version: str, sha256: str, release_date: str) -> dict[str, str]:
    url = f"{REPO}/releases/download/v{version}/SS14AutoJoin-{version}-windows-x64.exe"
    version_manifest = f"""# yaml-language-server: $schema=https://aka.ms/winget-manifest.version.{SCHEMA}.schema.json
PackageIdentifier: {IDENTIFIER}
PackageVersion: {version}
DefaultLocale: en-US
ManifestType: version
ManifestVersion: {SCHEMA}
"""
    installer = f"""# yaml-language-server: $schema=https://aka.ms/winget-manifest.installer.{SCHEMA}.schema.json
PackageIdentifier: {IDENTIFIER}
PackageVersion: {version}
InstallerType: portable
ReleaseDate: {release_date}
Installers:
- Architecture: x64
  InstallerUrl: {url}
  InstallerSha256: {sha256.upper()}
  PortableCommandAlias: SS14AutoJoin
ManifestType: installer
ManifestVersion: {SCHEMA}
"""
    locale = f"""# yaml-language-server: $schema=https://aka.ms/winget-manifest.defaultLocale.{SCHEMA}.schema.json
PackageIdentifier: {IDENTIFIER}
PackageVersion: {version}
PackageLocale: en-US
Publisher: Devigami
PublisherUrl: https://github.com/devigami
PublisherSupportUrl: {REPO}/issues
PackageName: SS14 Auto-Join
PackageUrl: {REPO}
License: MIT
LicenseUrl: {REPO}/blob/master/LICENSE
ShortDescription: Joins a full Space Station 14 server the moment a player slot opens, through the official launcher.
Description: |-
  SS14 Auto-Join watches one Space Station 14 server's public player count and, when a slot opens, tells the
  official launcher to connect, exactly as if you had pressed Connect. It confirms the join, plays a fanfare and
  leaves you in the game; a rejected attempt is closed and watching resumes. It never touches your account and
  cannot bypass server rules. Tested on Windows with the Steam edition of the launcher.
Moniker: ss14-autojoin
Tags:
- game
- launcher
- space-station-14
- ss14
ReleaseNotesUrl: {REPO}/releases/tag/v{version}
Documentations:
- DocumentLabel: Documentation
  DocumentUrl: https://devigami.github.io/ss14-autojoin/
ManifestType: defaultLocale
ManifestVersion: {SCHEMA}
"""
    return {
        f"{IDENTIFIER}.yaml": version_manifest,
        f"{IDENTIFIER}.installer.yaml": installer,
        f"{IDENTIFIER}.locale.en-US.yaml": locale,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    version, sha256 = argv[0], argv[1]
    release_date = argv[2] if len(argv) > 2 else date.today().isoformat()
    if len(sha256) != 64:
        print("the second argument must be the 64-hex-digit SHA-256 of the Windows window executable")
        return 2
    out = ROOT / "packaging" / "winget" / "manifests" / "d" / "Devigami" / "SS14AutoJoin" / version
    out.mkdir(parents=True, exist_ok=True)
    for name, text in manifests(version, sha256, release_date).items():
        (out / name).write_text(text, encoding="utf-8")
        print(f"wrote {out / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
