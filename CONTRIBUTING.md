# Contributing

Thanks for helping. This is a small tool with a narrow job, so the bar is: keep it correct, keep it polite to
servers, keep it simple.

## Setup

```
git clone https://github.com/devigami/ss14-autojoin
cd ss14-autojoin
uv sync --all-groups        # installs Python 3.14 and all dependencies
uv run pytest
uv run ruff check --fix . && uv run ruff format .
uv run mkdocs serve         # documentation preview at http://127.0.0.1:8000
```

## Ground rules

* **The launcher and the engine are the specification.** A claim about how they behave goes into
  `docs/development/launcher-reference.md` with the source file and commit it was read from, marked verified or
  not. Real logs that prove behaviour go into `docs/development/fixtures/`, redacted.
* **Never close a game client without evidence that it failed.** Silence is not failure.
* **Be a polite client.** No polling faster than once a second, one connection attempt per free slot, no
  bypassing server rules. Pull requests that add either will not be merged.
* **Windows-only code stays behind an interface** with a fake for tests (see `joiner.Ports` and `runtime.py`).
* Logic in importable modules; the window stays thin; the PyInstaller entry scripts are imported by nothing.
* Dependencies: standard library first, `psutil` for processes. Anything else needs a line in
  `docs/development/decisions.md`.

## Pull requests

Open them against `master`. CI runs the tests on Linux and Windows and builds the executables. Label the PR
`bug`, `enhancement`, `documentation` or `breaking`; the release notes are generated from those labels. A
maintainer bumps the version in `pyproject.toml` and `src/ss14_autojoin/__init__.py`; when that lands on
`master`, the release workflow tags it and publishes the binaries.

## Releasing (maintainers)

1. Bump `version` in `pyproject.toml` and `__version__` in `src/ss14_autojoin/__init__.py` (same value).
2. Merge to `master`. The `release` workflow sees a version without a tag, builds Windows and Linux
   binaries, and publishes `v<version>` with generated notes and checksums.
3. The `docs` workflow publishes the documentation site on every change to `docs/`.
4. The `winget` job of the release workflow submits the new version to `microsoft/winget-pkgs` when the
   `WINGET_TOKEN` secret is set; the first version of the package is submitted by hand
   (`packaging/winget/README.md`).
