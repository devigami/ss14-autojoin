# Security policy

SS14 Auto-Join is a small desktop tool. Its security surface is correspondingly small, but it does start and
stop processes on your machine, so problems in that area matter. This page says what the tool does with your
system, how to report a vulnerability, and what to expect.

## Supported versions

Only the latest release on the [releases page](https://github.com/devigami/ss14-autojoin/releases/latest)
receives fixes. Older versions are not patched; upgrade to the current release before reporting.

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Use GitHub's private vulnerability reporting:
open the repository's **Security** tab and choose **Report a vulnerability**, or go directly to
<https://github.com/devigami/ss14-autojoin/security/advisories/new>. The report reaches the maintainer only.

Include what you can: the version, your operating system, what the tool did, what it should have done, and
steps or a log that reproduce it. A proof of concept is welcome; a working exploit against other people's
machines or servers is not needed and should not be shared.

You can expect an acknowledgement within a week, a fix or a clear answer within a month for anything
confirmed, and credit in the release notes if you want it. If the report concerns the Space Station 14
launcher, engine or game rather than this tool, it will be passed on to the
[Space Wizards](https://github.com/space-wizards) with your consent, since those projects are theirs.

## What the tool does on your machine

Knowing this makes it easier to judge what is in scope.

* **Network.** HTTP `GET` requests to the server address you configure, for its public `/status` page, and
  nothing else. No telemetry, no update checks, no other hosts. TLS is used when the address is `ss14s://`.
* **Processes started.** The official launcher executable (`bin_x64\SS14.Launcher.exe` under the folder you
  configure or that was detected) with the server address as its only argument, and with `DOTNET_ROOT`
  pointing at the launcher's own bundled runtime. The tool never starts the game client itself.
* **Processes stopped.** Only a game client process (`SS14.Loader.exe`) whose ID the launcher's own log
  reported for an attempt the tool made, and only after evidence that the server rejected it. The process
  name is checked before termination. With the optional *Restart a stuck launcher* setting, the launcher
  process is also terminated and restarted.
* **Files read.** The launcher's logs (`launcher-*.log`, `client.stdout.log`) in the launcher's data folder,
  Steam's `libraryfolders.vdf` to find installations, and the Windows registry value for Steam's install path.
* **Files written.** `%APPDATA%\ss14-autojoin\config.toml`, the settings file. Nothing else.
* **Credentials.** None. The tool never reads, stores or transmits your Space Station 14 account, token or
  password; those stay inside the official launcher.

Reports about any behaviour outside this list are in scope and welcome, as are reports about the safety of
process termination, path handling in installation discovery, and parsing of the launcher and client logs
(which are inputs the tool reads but does not control).

## Out of scope

* The rules of individual game servers, and whether a server allows automated rejoining. Those are for the
  server's administrators.
* Vulnerabilities in Space Station 14, its launcher or the Robust engine. Report those to the Space Wizards.
* Issues that require an attacker to already control your user account or the launcher installation.

## Binaries and supply chain

Release executables are built by GitHub Actions from the tagged source, with no manual steps, and each release
carries a `SHA256SUMS.txt`. The executables are **not code-signed**, so Windows SmartScreen will warn on first
run; verify the checksum or build from source (`uv run python build.py`) if that matters to you. Dependencies
are pinned in `uv.lock`; the only runtime dependency beyond the standard library is `psutil`.
