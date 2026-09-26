# SS14 Auto-Join

[![ci](https://github.com/devigami/ss14-autojoin/actions/workflows/ci.yml/badge.svg)](https://github.com/devigami/ss14-autojoin/actions/workflows/ci.yml)
[![release](https://img.shields.io/github/v/release/devigami/ss14-autojoin?display_name=tag)](https://github.com/devigami/ss14-autojoin/releases/latest)
[![docs](https://img.shields.io/badge/docs-devigami.github.io%2Fss14--autojoin-blue)](https://devigami.github.io/ss14-autojoin/)
[![licence](https://img.shields.io/github/license/devigami/ss14-autojoin)](LICENSE)

**Get into a full [Space Station 14](https://spacestation14.com/) server without hammering the Connect button.**

SS14 Auto-Join watches one server's public player count and, the moment a slot opens, tells the official
launcher to connect, exactly as if you had pressed Connect yourself. It confirms that you got in, plays a short
fanfare, and leaves you in the game. If someone else took the slot first, it closes the rejected game client
and goes back to watching.

> **Tested on Windows only.** Everything has been verified on Windows 11 with the Steam edition of the
> launcher. Linux builds are produced but untested, and the standalone launcher has not been tried. If
> anything does not work for you, please **[open an issue](https://github.com/devigami/ss14-autojoin/issues/new/choose)**
> with the log from the window; the templates say what to include.

**Documentation: <https://devigami.github.io/ss14-autojoin/>** (getting started, settings, how it works,
troubleshooting, FAQ).

## Quick start

1. Download `SS14AutoJoin-<version>-windows-x64.exe` from the
   [latest release](https://github.com/devigami/ss14-autojoin/releases/latest) and run it. Windows may warn that
   the file is unsigned; choose *More info*, *Run anyway*.
2. The launcher folder is detected automatically (a running launcher, its log, your Steam libraries). Enter
   the server's `ss14://` or `ss14s://` address, or keep the default.
3. Press **Start watching**. The log shows the player count, the attempt, and `joined`.

Prefer a terminal? `ss14-autojoin-<version>-windows-x64.exe join ss14s://lizard.spacestation14.io/server`.
From source, with [uv](https://docs.astral.sh/uv/): `uv sync --all-groups`, then `uv run ss14-autojoin gui`.

## How it works, briefly

```
watch /status every 3 s ──▶ players < cap ──▶ run the launcher with the address ──▶ client starts
       ▲                                                                                 │
       └── rejected: close the client, read the reason, wait 2 s ◀── watch its UDP socket ─┤
                                                                       socket held 15 s ──▶ joined, fanfare
```

* **Through the real launcher.** The launcher holds your login, the content and the engine; the tool only
  hands it a server address, the same way `ss14://` links do. Your account is never touched.
* **Fair.** One attempt per free slot, polling no faster than once a second, and no way around server rules:
  a full server rejects it exactly as it would reject you. Bans, whitelists and the panic bunker stop it.
* **Careful.** A game client is only ever closed on evidence that the server rejected it. When in doubt the
  tool leaves the game running and stops.

The full explanation, including how the join is detected from the client's network socket because the
launcher does not flush the client log, is in [How it works](https://devigami.github.io/ss14-autojoin/how-it-works/).

## Settings

Everything is in the window and saved to `%APPDATA%\ss14-autojoin\config.toml`: launcher folder, server,
poll interval, extra free slots, decision timeout, cooldown, max attempts, rejoin, restart a stuck launcher,
skip while panic bunker is on, what to do when unsure (keep the game or retry), and the fanfare. Details in
[Settings](https://devigami.github.io/ss14-autojoin/settings/).

## Development

```
uv sync --all-groups                               # Python 3.14 and all dependencies, via uv
uv run pytest                                      # 89 tests, including real-log fixtures
uv run ruff check --fix . && uv run ruff format .
uv run mkdocs serve                                # the documentation site
uv run python build.py [--cli]                     # one-file executables into dist/
```

The design, the verified facts about the launcher and engine (with the source commits they were read from),
the decisions and the history are under [docs/development](docs/development/). See
[CONTRIBUTING.md](CONTRIBUTING.md) for the ground rules and the release process: merging a version bump to
`master` publishes a GitHub release with binaries and generated notes.

## AI disclosure

This project was written with substantial help from Claude Code, Anthropic's AI coding assistant, working
under the direction of a human maintainer who set the goals, supplied real logs from a Windows machine,
tested every milestone against live servers and reviewed the results. The launcher and engine behaviour it
relies on was read from the open-source code of those projects and checked against real logs; the
[reference](docs/development/launcher-reference.md) cites the files and commits. Bugs are the maintainer's
responsibility; please report them.

## Licence, privacy and affiliation

MIT, see [LICENSE](LICENSE). The tool collects no data; see [PRIVACY.md](PRIVACY.md) and the
[security policy](SECURITY.md). The bundled sound and icon are generated by scripts in `tools/` and are public
domain. This is an independent community tool and is not affiliated with or endorsed by Space Wizards
Federation. Space Station 14 is their game; play by each server's rules.
