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

## 2026-09-25 (later): first real logs from Windows

* Jacob supplied `client.stdout.log` for a successful join to Lizard and for a "server is full" attempt
  (`docs/fixtures/`, redacted). The success log confirms the line wording from the engine source, including
  the quoted endpoints and the harmless `Disconnected, reason: "Connection attempt failed"` of the losing
  IPv6/IPv4 candidate.
* The failure log ends before any `net:` line. Cause found in `Connector.PipeOutput`: the launcher writes the
  piped stdout into a `FileStream` with a 4 KiB buffer and never flushes, so a quiet failed client leaves its
  failure lines in memory. Consequence for the design: failure is detected by the absence of the success
  marker within a timeout, then the client is closed and the log read post-mortem (flush on exit unverified;
  new hand-off item 3).
* Checked and ruled out: `SS14_LOG_CLIENT` (unused by the engine), `log.*` cvars (server only), client
  `--loglevel`/`--cvar` flags (only the launcher builds the client command line). Root level is already Debug.

## 2026-09-25 (later still): the denial, seen

* Jacob repeated the full-server attempt and copied the log after pressing Exit
  (`docs/fixtures/client.stdout.full-after-exit.log`). The buffer is flushed on client exit. The denial arrives
  during the handshake: `Status changed to Disconnected, reason: "{\"reason\":\"Connect denied: The server is
  full!\",\"redial\":false,\"delay\":30}"`, then `Runlevel changed to: Initialize` and an `[ERRO] net: Exception
  during handshake` line with the same JSON. The parser in M2 has real text for both outcomes.

## 2026-09-26: the launcher log

* Jacob's launcher log (`docs/fixtures/launcher.log`) shows a **Steam** launcher, 0.40.1.0, at
  `D:\SteamLibrary\steamapps\common\Space Station 14 Playtest`, same layout as the standalone zip, client
  gets `--cvar branding.steam=true`. Target server confirmed as Lizard, address
  `ss14s://lizard.spacestation14.io/server` (status URL `https://lizard.spacestation14.io/server/status`).
* The launcher log has timestamps, the client PID (`Setting up manual-pipe logging for new client with PID`)
  and the client's exit (`EOF, ending pipe logging`), so it is the clock for the attempt timeout. Update with a
  cached version takes 1.6 s, with a content download 8.2 s (39 blobs).
* Decision: proceed with the Steam build; hand-off item 2 (command-line connect) is now the gating test.
* Added the Lizard address to the `server.py` test vectors.
