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

## 2026-09-26 (later): the Steam launcher takes commands; discovery module

* Jacob ran `bin_x64\SS14.Launcher.exe ss14s://lizard.spacestation14.io/server` against the running Steam
  launcher: the client started and attempted the join (denied, server full). The gating test passed; the
  join milestone is unblocked. He reports a `dotnet_x86` folder in the install.
* Jacob asked for (1) a matrix of common install locations checked before asking, (2) a configuration
  window. Both recorded in the plan; the GUI moved into M3 as required.
* Built `launcher.py`: install description (`LauncherInstall`), runtime folder detection, Steam library
  discovery through `libraryfolders.vdf`, root from the launcher log's `Launch command`, root from a running
  launcher process (psutil), common standalone folders, and `find_launcher` in priority order. `doctor` CLI
  command prints the result. 54 tests pass. `psutil` added as the first runtime dependency.

## 2026-09-26 (evening): cold start works; install layout confirmed

* `dir` of the install: `bin` (2025 leftover), `bin_x64`, `dotnet_x64`, `console.bat`, the bootstrap exe. The
  earlier `dotnet_x86` was a misreading.
* The command-line connect works with the launcher closed too: it starts, queues `r` and `c<uri>`, logs in,
  connects; client PID 5.7 s after start. Warm: `Connect command` to `Launch command` 3.2 s. The launcher log
  has `Launcher command: ...` lines for pipe/command-line connects. Fixture `launcher.log` extended.
* Consequence: no "launcher must be running" precondition; restarting a stuck launcher with the URI is a
  clean recovery.

## 2026-09-26 (night): M2 code complete, untested on Windows

* `client.py`: client log parsing (`ClientLogState`, `DenyReason` with escaped-JSON decoding), launcher log
  events with timestamps, `LogTail` (growth, recreation, partial lines) and `LauncherLogTail` (daily roll).
  Verified against all four fixtures: joined, truncated-while-open, full-after-exit, launcher log.
* `joiner.py`: the state machine with injected ports; 9 scripted scenarios (slot opens, full then join,
  timeout with post-mortem ban stops, unknown failures cap, no client appears, dropped command with and
  without restart, offline back-off and max attempts, panic bunker filter and stop, rejoin after kick).
* `runtime.py`: real ports (subprocess for the launcher command with `DOTNET_ROOT`, psutil for the client
  process, the two log tails). `join` CLI command wired. 76 tests pass. Hand-off item 7 is the first real run.

## 2026-09-26 (day 2): first real run, one wrong kill, the socket witness

* First `join` run on Windows: discovery, slot detection (three attempts, each on a `79/80` poll), the connect
  command, PID pick-up and termination all worked. But the client log never flushed after a successful join
  either (lobby with the rules popup is quiet), the tool saw no success marker in 45 s, and killed a live
  session. Jacob also read the behaviour as brute force; it was slot-driven, the server hovered at the cap.
* Fix: (1) unknown outcome now keeps the client and stops the tool (`--on-unknown retry` restores the old
  behaviour); (2) new witness: the client's open UDP socket count via psutil (0 after a rejection since Lidgren
  peers are shut down, 1 while connected). Joined after 15 s of an open socket, failed after 12 s with none.
  `probe` command to check the signal on Windows. 79 tests.

## 2026-09-26 (day 2, later): the socket witness is real

* `probe` on Windows: connected client `udp_sockets=1` every second, rejected client `udp_sockets=0`, no
  elevation needed. The join/fail decision no longer depends on the client log flushing. Also fixed a patch
  that had not applied (the `probe` subcommand and `--on-unknown` were missing from the parser) and added a
  test tying the parser's subcommands to the dispatch table.

## 2026-09-26 10:35: first end-to-end join

* `join ss14s://lizard.spacestation14.io/server --verbose --max-attempts 3`: poll `78/80 slot free` → connect
  command → client PID 32008 after 2 s → `joined (client kept a UDP socket open for 15 s)` → stop, game left
  running. 17 s from slot to confirmed join. M2 verified on Windows.
