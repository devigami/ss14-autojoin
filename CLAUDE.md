# ss14-autojoin

A Windows tool that watches one Space Station 14 server and, when a player slot is free, makes the official
launcher connect, verifies the join, and retries after rejections until the player is in. Public, MIT, 1.0.0.

Read in this order at the start of a session: this file, `docs/development/plan.md` (design),
`docs/development/launcher-reference.md` (verified platform facts), `docs/development/history.md` (what
happened, newest last), `docs/development/verification.md` (what was checked on a real machine).

## Status (update this section every session)

* **1.0.0**: all milestones complete and verified on the reference Windows machine (Windows 11, Steam launcher
  0.40.1.0, Robust 290.0.0): discovery, slot detection, connect through the launcher, join confirmation from the
  client's UDP socket, the window with settings, the config file, the fanfare, the icon, the one-file builds.
* **Release process**: merging a version bump to `master` triggers `.github/workflows/release.yml`, which
  builds Windows and Linux binaries and publishes `v<version>` with generated notes. `docs.yml` publishes the
  MkDocs site to GitHub Pages on changes under `docs/`.
* **Untested**: Linux and macOS joining, the standalone (non-Steam) launcher. Issue templates ask for the logs.

## Stack and commands

Python 3.14, uv, `pyproject.toml`, src layout, ruff, pytest, MkDocs Material for the docs, PyInstaller
`--onefile` for the binaries. Standard library for HTTP; `psutil` for processes. No other runtime dependency
without a line in `docs/development/decisions.md`.

```
uv sync --all-groups                                   # first time; Python 3.14 comes from uv
uv run pytest                                          # tests (must pass before every push)
uv run ruff check --fix . && uv run ruff format .      # lint and format (CI runs both in check mode)
uv run mkdocs build --strict                           # docs must build cleanly (CI checks)
uv run ss14-autojoin status|watch|join|doctor|probe|gui
uv run python build.py [--cli]                         # one-file exe into dist/ (window, or console tool)
uv run python tools/make_fanfare.py                    # regenerate the join sound
uv run python tools/make_icon.py                       # regenerate the icon
```

If `uv python install 3.14` offers only a release candidate, the container's uv is stale: `python3 -m pip
install --user --upgrade uv` puts a current uv in `~/.local/bin`.

## Layout

```
README.md, CONTRIBUTING.md, LICENSE
pyproject.toml, uv.lock   project and pins (lock is committed); version lives here and in __init__.py
mkdocs.yml, docs/         the user documentation site; docs/development/ holds the design, reference,
                          decisions, verification record, history and the real-log fixtures
src/ss14_autojoin/        server.py (addresses, /status), launcher.py (install discovery), client.py (log
                          parsing, tails), joiner.py (state machine, injected ports), runtime.py (real ports),
                          config.py (TOML settings), app.py (Tkinter window), notify.py (sounds), cli.py,
                          gui_main.py and cli_main.py (PyInstaller entry scripts, imported by nothing),
                          data/ (fanfare.wav, icon.png, icon.ico; generated, public domain)
tools/                    make_fanfare.py, make_icon.py
tests/                    pytest; fake HTTP server; fixtures under docs/development/fixtures/
.github/workflows/        ci.yml (tests, docs build, Windows artifact), docs.yml (Pages), release.yml
.github/ISSUE_TEMPLATE/   join problem, launcher not found, other platform, feature request
build.py                  PyInstaller --onefile builds (window and console)
```

## Rules for this project

* **The code is the specification.** A claim about the launcher, engine or content goes into
  `docs/development/launcher-reference.md` with the file and commit it was read from, marked verified or not.
  Sparse clones for reading: `git clone --depth 1 --filter=blob:none --sparse <url>` then
  `git sparse-checkout set <dirs>` for `space-wizards/SS14.Launcher`, `RobustToolbox`, `space-station-14`.
* **Everything Windows-only is behind an interface** (`joiner.Ports`, `runtime.py`) with a fake for tests.
  Never claim a Windows step works because the fake passed; record real checks in `verification.md`.
* **The tool never touches the account token** and never bypasses server rules: it only asks the launcher to
  connect, and stops retrying on reasons that are not "full" (ban, whitelist, panic bunker).
* **Be a polite client**: poll no faster than 1 s, default 3 s; one connect attempt per free slot; back off
  when the server is offline.
* **Never close a game client without evidence that it failed.** Silence is not failure (the launcher does
  not flush the client log while the client is quiet); when unsure, keep the client and stop.
* Logic in importable modules with a headless CLI; the GUI stays thin. Never import an entry script.
* Dated entries in `docs/development/history.md`; choices in `docs/development/decisions.md`; both before
  pushing. No personal names, account ids or machine-specific paths in the repository: use `<user>`,
  `<Steam library>`, `PLAYER_NAME` in fixtures.
* Configuration through flags and a TOML file; no secrets in the repository.

## Traps on record

* Python 3.14 ships Tk 9.0.4; on Windows `iconbitmap` reports success without changing the title bar, so
  `app.py` also sends `WM_SETICON` through ctypes after the window is mapped.
* The launcher writes `client.stdout.log` through an unflushed 4 KiB buffer: while the client is quiet
  (rejected, or waiting in the lobby) the file shows neither outcome. Decide from the UDP socket.
* Patches that anchor on source lines can silently miss after `ruff format`; assert the anchor matched.

## Git

Work on the branch the session names; commit with a clear message; push with `git push -u origin <branch>`.
Do not open a pull request unless asked. Keep `uv.lock` committed. Default branch: `master`.
