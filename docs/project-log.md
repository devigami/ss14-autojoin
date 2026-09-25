# Project log

Dated entries, newest last. Numbers where there are numbers.

## 2026-09-25: research, plan, scaffold (M0)

* Read the knowledge base (`devigami/ss14-knowledge`, 7 files) and the source of the launcher (`437fe66`),
  engine (`61bbd3f`, sparse) and content (`49b0dca`, sparse). Facts that matter are in
  `docs/ss14-launcher-reference.md` (13 sections); the design in `docs/plan.md`.
* Key findings: the launcher takes a `ss14://` URI on its command line and forwards it to a running instance
  over a named pipe; the Windows bootstrap exe drops arguments, so the tool must call `bin_x64\SS14.Launcher.exe`
  with `DOTNET_ROOT` set; the game client stays open on "The server is full!" with a 30 s Retry timer and never
  retries by itself; its stdout is written to `logs\client.stdout.log`, which is the signal for success or
  failure; a launcher overlay left in an error state silently drops later connect commands.
* Environment: cloud container blocks `hub.spacestation14.com` (proxy 403) but reaches GitHub. uv upgraded
  0.8.17 → 0.12.19 via pip to get Python 3.14.7 (the old uv only knew 3.14.0rc2).
* Scaffold: `pyproject.toml` (uv, ruff, pytest), `src/ss14_autojoin/server.py` (address parsing with the
  launcher's four test vectors, status parsing, free-slot logic, status fetch), `cli.py` with `status` and
  `watch` (poll and print), tests, CI workflow, `CLAUDE.md`.
