## What and why

<!-- One paragraph. Link the issue if there is one. -->

## How it was tested

<!-- `uv run pytest` is required. Say whether you ran it on Windows against a real server, and paste the tool's log if so. -->

## Checklist

- [ ] Tests and `ruff` pass (`uv run pytest`, `uv run ruff check . && uv run ruff format --check .`)
- [ ] Behaviour that depends on the launcher or engine is backed by a note in `docs/development/launcher-reference.md`
- [ ] Documentation updated if settings, commands or behaviour changed
- [ ] Labelled `bug`, `enhancement`, `documentation` or `breaking` so the release notes sort it correctly
