# ss14-autojoin

Watches a [Space Station 14](https://spacestation14.com/) server and, the moment a player slot is free, makes
the official launcher connect, exactly as the Connect button would. If the join fails (someone else took the
slot), it closes the failed game client and goes back to watching until you are in.

**Status (2026-09-26):** the full loop exists (`join`): watch the server, connect through the launcher when a
slot is free, verify from the client log, close a rejected client and try again. Verified end to end on Jacob's
Windows machine on 2026-09-26 (joined Lizard on the first free slot). The window with the settings panel
(`ss14-autojoin gui`) and the one-file Windows executables (built by CI on every push) are verified too. See `docs/plan.md` for the design and
`docs/handoff.md` for what still needs a Windows machine.

## Run

Requires [uv](https://docs.astral.sh/uv/); Python 3.14 is installed by uv.

```
uv sync --all-groups
uv run ss14-autojoin status ss14://server.example.org        # one status fetch (scheme optional, port defaults to 1212)
uv run ss14-autojoin status ss14://server.example.org --json
uv run ss14-autojoin watch  ss14://server.example.org --interval 3   # print whenever the slot situation changes
uv run ss14-autojoin doctor                                          # find the launcher install and its data folders
uv run ss14-autojoin join ss14s://lizard.spacestation14.io/server --verbose   # the auto-join loop
uv run ss14-autojoin gui                                             # the window (settings, Start/Stop, log)
uv run python build.py            # dist/SS14AutoJoin.exe (window); add --cli for dist/ss14-autojoin.exe
uv run pytest
```

## Layout

* `src/ss14_autojoin/` the code: `server.py` (addresses, `/status`), `launcher.py` (finding the install),
  `client.py` (reading the client and launcher logs), `joiner.py` (the loop, with injected ports),
  `runtime.py` (real processes and files), `config.py` (settings file), `app.py` (the window), `cli.py`.
* `build.py` PyInstaller one-file builds; CI uploads the Windows executables on every push.
* `tests/` pytest, with a local fake status server.
* `docs/` `plan.md`, `ss14-launcher-reference.md` (verified facts about the launcher, engine and content),
  `decisions.md`, `handoff.md`, `project-log.md`.
* `CLAUDE.md` operating instructions for the coding sessions.

Conventions follow the `devigami/ss14-knowledge` project template. Deviation: CI also runs the tests on
Windows, because that is where the tool runs.

## Licence

MIT, see `LICENSE`.
