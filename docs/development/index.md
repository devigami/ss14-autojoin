# Development

These pages are the working record behind the tool: the design, what was verified against the launcher and
engine source, the decisions taken, and the history. They are kept because the behaviour of the launcher and
the game client is the specification the tool depends on.

* [Plan and design](plan.md): the state machine, the detection method and the milestones.
* [Launcher and engine reference](launcher-reference.md): verified facts about the SS14 launcher, the Robust
  engine and the game client, with the source files and commits they were read from.
* [Decisions](decisions.md): choices made along the way and the alternatives considered.
* [Verification record](verification.md): what was checked on a real Windows machine.
* [History](history.md): a dated log of the work.

## Working on the code

```
uv sync --all-groups            # Python 3.14 comes from uv
uv run pytest                   # tests
uv run ruff check --fix . && uv run ruff format .
uv run mkdocs serve             # this documentation, live
uv run python build.py [--cli]  # executables into dist/
```

Layout: `src/ss14_autojoin/` holds the code (`server.py` status and addresses, `launcher.py` install discovery,
`client.py` log parsing, `joiner.py` the loop with injected ports, `runtime.py` the real processes and files,
`config.py`, `app.py` the window, `cli.py`); `tests/` are pytest with a fake status server and the real-log
fixtures under `docs/development/fixtures/`; `tools/` regenerates the bundled sound and icon.

Contributions are welcome; see `CONTRIBUTING.md` in the repository.
