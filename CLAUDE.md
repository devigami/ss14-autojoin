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
* **1.0.1 in progress, not released**: the version is still 1.0.0 everywhere on purpose, because the bump is
  the release trigger. Done so far: `SS14AutoJoin --version` (window build, through `console.py`), the
  version in the title bar, user docs that recommend winget, start-up smoke checks for every build in CI and
  before a release, the Linux Tcl/Tk bundling fix, the winget fork owner from a repository variable.
  Still to check by hand on Windows before releasing: see "Not verified" in `verification.md`.
* **winget**: `Devigami.SS14AutoJoin` 1.0.0 is in `microsoft/winget-pkgs` (PR 441430, merged 2026-11). Its
  manifest pins the SHA-256 of the 1.0.0 release asset, so that asset must never be replaced or re-signed.
  Later versions go through the `winget` job in `release.yml`, which needs the `WINGET_TOKEN` secret and the
  `WINGET_FORK_USER` variable (the account that owns the `winget-pkgs` fork).
* **Signing**: not yet, and no longer blocking: a winget install shows no SmartScreen prompt (read from the
  winget client source, not yet run on Windows; see `packaging/winget/README.md`). Direct downloads still
  warn. SignPath Foundation wants proof of popularity; the paid route under consideration is Microsoft
  Artifact Signing, as a `sign` job between `build` and `release`. Windows builds carry a version resource.

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
uv run python tools/smoke_version.py dist/<exe> ...    # a built exe must start and print this version
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
                          console.py (printing from the windowed build: stdout, std handle, parent console),
                          gui_main.py and cli_main.py (PyInstaller entry scripts, imported by nothing),
                          data/ (fanfare.wav, icon.png, icon.ico; generated, public domain)
tools/                    make_fanfare.py, make_icon.py, make_winget_manifest.py, smoke_version.py,
                          console_probe.py (plays the terminal for a windowed program, Windows only)
packaging/winget/         winget manifests (portable package Devigami.SS14AutoJoin) and how to submit them
tests/                    pytest; fake HTTP server; fixtures under docs/development/fixtures/
.github/workflows/        ci.yml (tests, docs build, Windows and Linux builds that must start), docs.yml
                          (Pages), release.yml (builds, smoke checks, release, winget submission)
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
* The window build is a GUI-subsystem program: `sys.stdout` is `None` unless the caller redirected it, and
  a shell does not wait for it. Anything it must say on the command line goes through `console.emit`.
  PowerShell waits only when something follows it in the pipeline (`app | Out-String` works, `$v = app` is
  empty and closes the pipe), so `emit` writes unbuffered: text left in a buffer fails again at exit.
* A one-file build is two processes: the bootloader and, as its child, the program. Handles are passed down
  through the bootloader, but "the parent's console" is the bootloader's, and it has none. Anything that
  means "the terminal I was started from" has to look further up (`console.attach_nearest_console`).
  Pipes cannot observe a console; `tools/console_probe.py` reads a real one.
* A PyInstaller build that finishes is not a build that starts. `uv python install 3.14` gives whatever
  patch release that uv knows (3.14.6 in a container with a stale uv, 3.14.10 on the CI runners), and
  on Linux the `_tkinter` of 3.14.6 has no RPATH: PyInstaller logs "Library not found: libtcl9.0.so" as a
  warning, finishes, and the window build dies on import. `build.tcl_tk_libraries` names the files; a build
  is not good until `tools/smoke_version.py` has started it.

## Git

Work on the branch the session names; commit with a clear message; push with `git push -u origin <branch>`.
Do not open a pull request unless asked. Keep `uv.lock` committed. Default branch: `master`.
