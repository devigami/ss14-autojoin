# Plan: SS14 auto-join

Written 2026-09-25 after reading the launcher, engine and content source (facts in
`ss14-launcher-reference.md`). Update this file when the design changes; record why in `decisions.md`.

## Goal

A tool on Jacob's Windows PC that watches one SS14 server and, the moment a player slot is free, makes the
official launcher connect exactly as the "Connect" button would. If the join fails (the slot was taken, or
anything else), it closes the failed game client and goes back to watching, until the player is in the game.

## Constraints that shape the design

1. **Joining must go through the real launcher.** The launcher owns the login token, the content database and
   the engine signature check; the client cannot be started without them (reference §8). The launcher accepts
   connect commands from outside through its command line or named pipe (§6), so the tool drives it that way.
2. **The launcher does not know whether the join succeeded.** It only tracks the client process (§7). The
   game client stays open on a "Failed to connect: The server is full!" screen and never retries or exits by
   itself (§9). Detecting the outcome and cleaning up is the tool's job.
3. **The cloud session cannot run any of the Windows side.** No launcher, no game, no hub (network policy
   blocks it). Everything that touches them is built behind interfaces, exercised with fakes and fixtures, and
   verified by Jacob through `handoff.md`.
4. **Be a polite client.** Poll `/status` at the launcher's own cadence or slower, never hammer a full server
   with connection attempts, and log everything the tool does.

## How a join attempt works, end to end

```
 watch                     decide                 join                       verify                  clean up
 GET /status every N s --> players < soft cap? --> SS14.Launcher.exe ss14://… --> tail client.stdout.log --> kill SS14.Loader.exe
 (5 s timeout, offline     (+ optional margin,     (pipe when launcher runs,    "Handshake completed"   on failure, cool down,
  handling)                 panic bunker, round     exe otherwise; DOTNET_ROOT   = joined;               back to watch
                            state filters)          set like the bootstrap)      "Status changed to
                                                                                 Disconnected …" = failed
```

## Components (`src/ss14_autojoin/`)

| Module | Responsibility | Testable in the cloud |
|---|---|---|
| `server.py` | parse `ss14://` addresses like the launcher does; build `/status` and `/info` URLs; fetch and parse `/status` into `ServerStatus`; free-slot logic | yes (unit tests with the launcher's test vectors; a local HTTP server for the fetch) |
| `watcher.py` | poll loop with interval, timeout, jitter and back-off; classify each poll as `offline` / `full` / `slot free`; emit state changes | yes (fake clock and fake fetch) |
| `launcher.py` | locate the launcher install (config, then `bin_x64\SS14.Launcher.exe` search) and data dirs; check the pipe; send `r`/`c<uri>` over the pipe or by starting the exe with `DOTNET_ROOT`; read the launcher log for `Connect command`, `Dropping connect command`, `Failed to connect`, `PID` | mostly (fake filesystem and fake process runner; the pipe write and exe start are thin adapters) |
| `client.py` | track the game client: PID from the launcher log or `SS14.Loader` processes started after the command (`psutil`); tail `client.stdout.log` from the start of the new file; classify lines into `connecting` / `joined` / `failed(reason, delay)` / `disconnected(reason)`; terminate the process | yes (fixture logs; a dummy process) |
| `joiner.py` | the state machine below; owns timeouts and cooldowns; drives watcher, launcher and client; emits events for the UI/CLI | yes (all dependencies injected) |
| `cli.py` | `ss14-autojoin status <address>`, `watch <address>` (poll and print), `join <address>` (the full loop), `servers <filter>` (hub lookup, Windows only), `doctor` (prints detected launcher install, runtime folder, log paths) | yes for parsing and `status`/`watch`/`doctor` |
| `config.py` | TOML settings file (`%APPDATA%\ss14-autojoin\config.toml`): launcher folder, server address, poll interval, margin, rejoin, restart-launcher flags; defaults filled from discovery | yes |
| `notify.py` | sound or toast when joined or stuck (later) | partly |
| `app.py` | Tkinter window over `joiner`: a status line, Start/Stop, and a **settings panel** for the game/launcher folder (with the detected value pre-filled and a Browse button), server address, poll interval, margin, options; writes `config.toml` (**required**, Jacob's request of 2026-09-26) | headless smoke only |

Configuration: command-line flags first, then a small TOML file (`%APPDATA%\ss14-autojoin\config.toml`) for the
launcher path and defaults. No secrets are involved: the tool never sees the account token.

## Finding the launcher (`launcher.py`, built 2026-09-26)

Order of candidates, first hit wins; each is a folder that must hold `bin_x64\SS14.Launcher.exe`
(`bin_arm64`, or `bin` for the Linux tarball):

1. The configured path (settings window or `--launcher`); it may point at the root, at `bin_x64`, or at the exe.
2. A **running launcher process** (`SS14.Launcher.exe` via psutil): its exe's grandparent is the root.
3. The **newest launcher log**'s `Launch command:` line, which names `<root>\bin_x64\loader\SS14.Loader.exe`.
4. **Steam libraries**: Steam's install dir from the registry (`HKCU\Software\Valve\Steam\SteamPath`),
   `%ProgramFiles(x86)%\Steam`, `%ProgramFiles%\Steam`, then every library listed in
   `steamapps\libraryfolders.vdf`, each checked for `steamapps\common\Space Station 14 Playtest` and
   `steamapps\common\Space Station 14`.
5. **Standalone zip spots**: `%LOCALAPPDATA%`, `%LOCALAPPDATA%\Programs`, Program Files, `Downloads`,
   `Desktop`, `Documents`, `Games`, the home folder, and `X:\Games`, `X:\` for drives C to F, each with the
   names `Space Station 14 Launcher`, `SS14.Launcher_Windows`, `SS14.Launcher`, `SS14 Launcher`.

The result records the source, the loader exe, and the bundled runtime folder (`dotnet_x64` preferred, any
`dotnet*` with `dotnet.exe` accepted, since Jacob's Steam install shows `dotnet_x86`). `ss14-autojoin doctor`
prints all of it. The settings window shows the detected path and lets the user override it.

## The state machine (`joiner.py`)

```
            +-----------+   slot free    +------------+  client PID seen   +------------+  "Handshake completed"  +----------+
  start --> | WATCHING  | -------------> | CONNECTING | -----------------> | VERIFYING  | ----------------------> |  JOINED  |
            +-----------+                +------------+                    +------------+                         +----------+
                 ^  ^                        |  no PID within 20 s /            |  "Status changed to Disconnected"        |
                 |  |                        |  "Dropping connect command"      |  / handshake exception /                |  optional: client exits or
                 |  |                        v                                  v  attempt timeout (90 s incl. download)   |  "Disconnected (...)"
                 |  |                   +-----------+                     +-----------+                                    |  with --rejoin
                 |  +-------------------|  STUCK    |                     |  FAILED   |------------------------------------+
                 |     after recovery   +-----------+                     +-----------+   kill SS14.Loader, wait until gone,
                 |     (opt-in: restart launcher)                              |          cool down (2 s; full → honour nothing
                 +-------------------------------------------------------------+          server-side, but wait `cooldown`)
```

Rules:

* **WATCHING**: poll every `interval` (default 3 s, minimum 1 s). Slot free when `players < soft_max_players
  - margin` (margin default 0; when `soft_max_players` is missing the server reports no cap and the tool
  treats it as joinable). Optional filters: skip while `panic_bunker` is true, or while `run_level` is
  `PostRound` (a fresh round start floods the server with joins; configurable). Offline polls back off to 10 s.
* **CONNECTING**: exactly one connect command per attempt. Before sending, make sure no `SS14.Loader` from a
  previous attempt is alive. Success of the *command* is a new `Connect command:` line in the launcher log
  or a client PID; failure is `Dropping connect command` or no client within 20 s.
* **VERIFYING**: tail the new `client.stdout.log` and count the client's UDP sockets every tick. Joined =
  `Handshake completed` / `Runlevel changed to: Connected` in the log, or a socket open for 15 s. Failed = a
  `Disconnected` for the winning endpoint or an `Exception during handshake` in the log, the client exiting,
  or 0 sockets after 12 s once connecting began. Nothing by 60 s = unknown: keep the client, stop the tool
  (`--on-unknown retry` to close it and try again instead).
* **FAILED**: terminate the client (`psutil` terminate, then kill after 5 s), confirm it is gone, wait
  `cooldown` (default 2 s), return to WATCHING. Log the reason. If the reason is not "full" (ban, whitelist,
  panic bunker, version mismatch), stop and tell the user: retrying will not help.
* **JOINED**: stop by default (the tool did its job). With `--rejoin`, keep watching the client and go back
  to WATCHING when it exits or logs a disconnect; note that a player who was in the round bypasses the cap on
  reconnect anyway (§5), so `--rejoin` mostly matters after a client exit.
* **STUCK**: the launcher is showing an errored overlay and drops connects (`Dropping connect command` in its
  log). Notify the user. With `--restart-launcher` (opt-in), terminate `SS14.Launcher.exe` and start it again
  with the URI, which both clears the overlay and queues the connect: verified on 2026-09-26 that a cold
  start with a URI logs in and connects by itself (about 6 s to the client).
* **Launcher not running** is not a special case: the same command starts it and queues the connect.

## Why this detection method

| Signal | Reliability | Latency | Used for |
|---|---|---|---|
| `client.stdout.log` lines (reference §10) | high wording-wise, **but the file lags up to 4 KiB of output behind the client**, and both a rejected client and one waiting in the lobby are quiet, so while the client lives the log usually shows neither outcome | seconds when it flushes; unbounded otherwise | early decision when it does flush; post-mortem classification after the client is closed |
| the client's open UDP sockets (reference §12a) | rejected: 0 (Lidgren peers shut down); connected: 1 for the whole session. Windows readability via psutil to be confirmed | seconds | **primary live decision**: 0 sockets after 12 s = failed; a socket open for 15 s = joined |
| absence of any evidence within the attempt timeout, client still alive | says nothing by itself | the timeout | **default: keep the client and stop** (never kill a possibly live session); `--on-unknown retry` closes it and tries again |
| launcher log (`Connect command`, `PID`, `Dropping`, `Failed to connect: ConnectionFailed`/`UpdateError`) | high | seconds (Serilog file sink) | command accepted, client PID, stuck detection, launcher-side failures |
| `SS14.Loader` process alive | high for "client exists", says nothing about the join | immediate | cleanup and sanity checks |
| `/status` players count rising after the attempt | weak (others join too; admins excluded; polling lag) | 3 to 5 s | corroboration only, never a decision |

Revised on 2026-09-26 after the first real run killed a client that had in fact joined (the log never
flushed; the tool treated silence as failure). VERIFYING now decides from three witnesses: the log when it
flushes, the client's UDP sockets, and the client's exit. Silence until the attempt timeout keeps the client
and stops the tool by default. After a decided failure the client is terminated and the log read post-mortem
(it flushes on exit) to classify the reason; unreadable reasons count towards a cap so a ban cannot loop.

## Cloud versus Windows

Built and tested here: everything in the table above with fakes, plus the `status`/`watch` CLI against a
local fake server. Needs Jacob (see `handoff.md`): the real launcher path, one real failed and one real
successful `client.stdout.log` to freeze the exact log wording into fixtures, the pipe test, the target server
address, and the end-to-end run. The Windows executable is built by CI (`windows-latest`) once `build.py`
exists.

## Milestones

1. **M0, this session**: research, this plan, project scaffold, `server.py` with tests, CI. Done when
   `uv run pytest` and `ruff` pass and the branch is pushed.
2. **M1, watch**: `watcher.py`, `cli.py status|watch`, fixtures, back-off. Jacob can run `ss14-autojoin watch
   ss14://<server>` on Windows and see slot changes.
3. **M2, join**: `launcher.py`, `client.py`, `joiner.py`, `cli.py join|doctor`, fixture logs from Jacob. First
   end-to-end join on Windows.
4. **M3, app**: `config.py`, the Tkinter window with the settings panel, stuck recovery, `--rejoin`, non-full
   reasons stop the loop, notifications, `build.py` and the Windows CI artifact, release `v0.1.0`.
5. **M4, optional**: hub lookup by server name in the settings panel.

## Open questions (answers go to `decisions.md`)

* Does the target server run panic bunker or a whitelist? (Changes which failures are retryable.)
* Should the tool honour the server's 30 s `delay` between attempts even though only the client UI enforces
  it? Current default: no, because a fresh client is never in the delay window and polling already spaces
  attempts by at least the client start-up time (10 s or more); keep `cooldown` configurable.
* Poll interval: 3 s default; the launcher's own list refresh is manual, so nothing to copy. Measure the
  status endpoint's latency on Windows before going lower.
