# ss14-autojoin

Watches a [Space Station 14](https://spacestation14.com/) server and, the moment a player slot is free, makes
the official launcher connect, exactly as the Connect button would. If the join fails (someone else took the
slot), it closes the failed game client and goes back to watching until you are in.

**Status (2026-09-25):** research and design done, project scaffolded. Today the tool can fetch and watch a
server's status; launching through the launcher is the next milestone. See `docs/plan.md` for the design and
`docs/handoff.md` for what still needs a Windows machine.

## Run

Requires [uv](https://docs.astral.sh/uv/); Python 3.14 is installed by uv.

```
uv sync --all-groups
uv run ss14-autojoin status ss14://server.example.org        # one status fetch (scheme optional, port defaults to 1212)
uv run ss14-autojoin status ss14://server.example.org --json
uv run ss14-autojoin watch  ss14://server.example.org --interval 3   # print whenever the slot situation changes
uv run pytest
```

## Layout

* `src/ss14_autojoin/` the code: `server.py` (addresses, `/status`), `cli.py`. Coming: `watcher.py`,
  `launcher.py`, `client.py`, `joiner.py`.
* `tests/` pytest, with a local fake status server.
* `docs/` `plan.md`, `ss14-launcher-reference.md` (verified facts about the launcher, engine and content),
  `decisions.md`, `handoff.md`, `project-log.md`.
* `CLAUDE.md` operating instructions for the coding sessions.

Conventions follow the `devigami/ss14-knowledge` project template. Deviation: CI also runs the tests on
Windows, because that is where the tool runs.

## Licence

MIT, see `LICENSE`.
