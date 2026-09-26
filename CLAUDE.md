# ss14-autojoin

A tool for Jacob's Windows PC that watches one Space Station 14 server and, when a player slot is free, makes
the official launcher connect, then verifies the join and retries after failures until the player is in.

Read in this order at the start of a session: this file, `docs/plan.md` (design and milestones),
`docs/ss14-launcher-reference.md` (verified platform facts), `docs/project-log.md` (what happened, newest
last), `docs/handoff.md` (what is waiting on Jacob). The knowledge base `devigami/ss14-knowledge` holds the
general SS14 notes and the conventions this project follows; clone it when you need it:
`git clone --depth 1 https://github.com/devigami/ss14-knowledge /home/user/ss14-knowledge`.

## Status (update this section every session)

* **Milestone**: M0 and M1 done 2026-09-25 (scaffold, `server.py`, `status`/`watch`); M2 code complete
  2026-09-26 (`launcher.py`, `client.py`, `joiner.py`, `runtime.py`, `join`). First Windows run: discovery,
  slot detection, connect, PID and termination worked; the join was missed because the client log never
  flushes while the client is quiet, and a live client was killed. Fixed with the UDP-socket witness and
  keep-on-unknown; awaiting the second run (hand-off item 7). Then M3 (`config.py`, Tkinter settings window,
  `build.py`, Windows CI artifact).
* **Have from Jacob (2026-09-25)**: a successful and a failed `client.stdout.log` (`docs/fixtures/`). The
  failed one revealed that the launcher does not flush the log while the client is quiet, so failure
  detection is timeout-based (`docs/plan.md`, "Why this detection method").
* **Known (2026-09-26)**: Steam launcher 0.40.1.0 at `D:\SteamLibrary\steamapps\common\Space Station 14
  Playtest`; target Lizard `ss14s://lizard.spacestation14.io/server`; all four fixtures in `docs/fixtures/`.
* **Verified 2026-09-26**: the Steam launcher accepts `bin_x64\SS14.Launcher.exe <uri>` and connects. Join
  milestone unblocked. `launcher.py` (install discovery) and `doctor` exist; next is `client.py` (log
  parsing, process tracking) and `joiner.py`, then the Tkinter settings window (M3, required).
* **Verified 2026-09-26 (evening)**: cold start with a URI works too (launcher starts, logs in, connects in
  about 6 s). Install has `bin_x64` and `dotnet_x64`.
* **Waiting on Jacob**: `probe` output (does psutil see the client's UDP socket on Windows?) and the second
  `join` run (`docs/handoff.md`, item 7).
* **Works today**: `status`, `watch`, `doctor` (Windows-verified), `join <address>` (Windows-run once, see
  above), `probe` (socket signal check).

## Stack and commands

Python 3.14, uv, `pyproject.toml`, src layout, ruff, pytest; PyInstaller `--onefile` for the Windows binary
(added in M3). Standard library for HTTP; `psutil` for processes. No other runtime dependencies
without a line in `docs/decisions.md`.

```
uv sync --all-groups                                   # first time; Python 3.14 comes from uv
uv run pytest                                          # tests (must pass before every push)
uv run ruff check --fix . && uv run ruff format .      # lint and format (CI runs both in check mode)
uv run ss14-autojoin status ss14://host[:port]         # one status fetch
uv run ss14-autojoin watch ss14://host --interval 3    # poll and print slot changes
uv run ss14-autojoin doctor                            # where the launcher and its logs are
uv run ss14-autojoin join ss14s://host/path --verbose  # the auto-join loop (Windows)
```

If `uv python install 3.14` offers only a release candidate, the container's uv is stale: `python3 -m pip
install --user --upgrade uv` puts a current uv in `~/.local/bin` (that is what happened on 2026-09-25).

## Layout

```
CLAUDE.md                 this file
README.md                 what it is, status, how to run
pyproject.toml, uv.lock   project and pins (lock is committed)
src/ss14_autojoin/        server.py (addresses, /status), launcher.py (install discovery), client.py (log
                          parsing, tails), joiner.py (state machine, injected ports), runtime.py (real ports),
                          cli.py; later config.py, notify.py, app.py (Tkinter settings window)
tests/                    pytest; fake HTTP server, fixture logs under docs/fixtures/
docs/                     plan.md, ss14-launcher-reference.md, decisions.md, handoff.md, project-log.md,
                          fixtures/ (real logs from Jacob's machine, redacted)
.github/workflows/ci.yml  ruff + pytest on Linux and Windows; Windows exe job once build.py exists
```

## Rules for this project

* **The code is the specification.** A claim about the launcher, engine or content goes into
  `docs/ss14-launcher-reference.md` with the file and commit it was read from, marked verified or not. The
  session keeps shallow or sparse clones at `/home/user/SS14.Launcher`, `/home/user/RobustToolbox`,
  `/home/user/space-station-14` (commands in the reference's header table; recreate them in a fresh
  container with `git clone --depth 1 --filter=blob:none --sparse <url>` then `git sparse-checkout set <dirs>`).
* **Everything Windows-only is behind an interface** (launcher location, pipe, process control, log paths)
  with a fake for tests and an entry in `docs/handoff.md` for the real check. Never claim a Windows step
  works because the fake passed.
* **The tool never touches the account token** and never bypasses server rules: it only asks the launcher to
  connect, and stops retrying on reasons that are not "full" (ban, whitelist, panic bunker).
* **Be a polite client**: poll no faster than 1 s, default 3 s; one connect attempt per free slot; back off
  when the server is offline.
* **Never close a game client without evidence that it failed.** Silence is not failure (the log does not
  flush while the client is quiet); when unsure, keep the client and stop.
* Logic in importable modules with a headless CLI; any GUI stays thin. Never import the entry script from
  another module (PyInstaller).
* Dated entries in `docs/project-log.md`; choices made for Jacob in `docs/decisions.md`; both before pushing.
* Configuration through flags and a TOML file; no secrets in the repository; Jacob's own logs go to
  `docs/fixtures/` only after redacting user ids and tokens.

## Git

Work on the branch the session names (currently `claude/fervent-euler-pc8uqv`); commit with a clear message;
push with `git push -u origin <branch>`. Do not open a pull request unless asked. Keep `uv.lock` committed.
