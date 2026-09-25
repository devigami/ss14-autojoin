# SS14 launcher and client: how a connection works

Platform facts for the auto-join tool, read from source on 2026-09-25. Everything here is **verified** against
the commits below unless a line says otherwise. When something matters, re-read the code; it is the
specification.

| Source | Commit | Date | Where the cloud session keeps it |
|---|---|---|---|
| `space-wizards/SS14.Launcher` | `437fe66` | 2026-09-16 | `/home/user/SS14.Launcher` (shallow clone) |
| `space-wizards/RobustToolbox` (engine) | `61bbd3f` | 2026-09-20 | `/home/user/RobustToolbox` (sparse: `Robust.Shared/Network`, `Robust.Shared/Log`, `Robust.Client/GameController`, `Robust.Server/ServerStatus`) |
| `space-wizards/space-station-14` (content) | `49b0dca` | 2026-09-25 | `/home/user/space-station-14` (sparse: `Content.Client/Launcher`, `Content.Server/Connection`, `Content.Server/GameTicking`, `Content.Shared/CCVar`) |
| `devigami/ss14-knowledge` | `d13d43b` | 2026-09-25 | `/home/user/ss14-knowledge` |

## 1. Server addresses

`SS14.Launcher/UriHelper.cs`, `Global.cs`, `SS14.Launcher.Tests/UriHelperTests.cs`.

* A server address is `ss14://host[:port][/path]` or `ss14s://host[:port][/path]`. Text without `://` gets
  `ss14://` prepended. Any other scheme, or an empty host, is invalid.
* The HTTP API base is the same URI with the scheme swapped: `ss14` → `http`, `ss14s` → `https`. When
  `ss14://` has no explicit port, the API port is **1212**. When `ss14s://` has no explicit port, it is 443
  (left implicit). The path is kept and given a trailing slash.
* Endpoints relative to the base: `status`, `info`, `client.zip` (and for ACZ servers `manifest.txt`,
  `download`).

Test vectors (the launcher's own tests):

| Input | Status URL |
|---|---|
| `server.spacestation14.io` | `http://server.spacestation14.io:1212/status` |
| `ss14s://server.spacestation14.io` | `https://server.spacestation14.io/status` |
| `ss14s://server.spacestation14.io:1212` | `https://server.spacestation14.io:1212/status` |
| `ss14s://server.spacestation14.io/foo` | `https://server.spacestation14.io/foo/status` |

The game connects over UDP to `/info`'s `connect_address` (a `udp://host:port` URI); when that is empty the
client uses the API host and port (`Connector.GetConnectAddress`). The engine defaults a `udp://` URI without a
port to 1212 (`GameController.ReadInitialLaunchState`).

## 2. `GET /status`

Engine (`Robust.Server/ServerStatus/StatusHost.Handlers.cs`) writes `name`, `players`, `tags`; the content's
`ServerGameTicker.StatusShell.cs` then overwrites/adds fields. Result for a stock content server:

```json
{
  "name": "Wizard's Den Lizard [NA West]",
  "map": "Box",
  "round_id": 12345,
  "players": 78,
  "soft_max_players": 80,
  "panic_bunker": false,
  "run_level": 1,
  "preset": "Secret",
  "round_start_time": "2026-09-25T09:00:00.0000000Z",
  "tags": ["region:am_n_w", "rp:low"]
}
```

* `players`: `PlayerCount` of the server's player manager, **minus active admins** unless the server sets
  `admin.admins_count_in_playercount` (default false).
* `soft_max_players`: the cvar `game.soft_max_players` (default 30). Servers without the content layer omit it.
* `run_level`: 0 `PreRoundLobby`, 1 `InRound`, 2 `PostRound`. `round_start_time` (ISO 8601, .NET "o" format)
  is only present from `InRound` onwards. `preset` only when a preset is chosen.
* The launcher marks a server **Offline** on any HTTP, JSON or socket error, or after **5 s**
  (`ConfigConstants.ServerStatusTimeout`). It clamps negative counts to 0.
* The launcher sends `User-Agent: SS14.Launcher/<version>` and a header `SS14-Launcher-Fingerprint`. Servers
  do not require either (unverified for every fork; the status endpoint is public).

## 3. `GET /info`

Fields (engine `StatusHost.Handlers.cs`, launcher `Models/ServerInfo.cs`): `connect_address`, `auth`
(`mode`, `public_key`), `build` (`engine_version`, `fork_id`, `version`, `download_url`, `hash`, `acz`,
`manifest_download_url`, `manifest_url`, `manifest_hash`), `desc`, `links`, `privacy_policy` (`identifier`,
`version`, `link`). The launcher fetches it at connect time and, in the server list, with `?can_skip_build=1`.

## 4. The hub

`SS14.Launcher/Api/HubApi.cs`, `ConfigConstants.cs`. `GET https://hub.spacestation14.com/api/servers`
returns `[{ "address": "ss14://...", "statusData": { ...the status JSON... } }]`. Fallback host
`hub.fallback.spacestation14.com`. `api/servers/info?url=<address>` proxies a server's `/info`. The cloud
container's network policy blocks `hub.spacestation14.com` (proxy 403), so hub access is a Windows-side step.

## 5. Who gets in: the server's admission rules

`Content.Server/Connection/ConnectionManager.cs` (`ShouldDeny`, `NetMgrOnConnecting`), cvars in
`Content.Shared/CCVar/CCVars.Game.cs` and `CCVars.Admin.cs`. Checks run in this order for each connecting
player:

1. Ban (`ConnectionDenyReason.Ban`).
2. A temporary bypass granted by an admin skips everything below.
3. Panic bunker (`game.panic_bunker.enabled`), non-admins only.
4. **Soft player cap**: with `softPlayerCount = PlayerCount` (minus active admins unless
   `admin.admins_count_for_max_players`, default false), deny when
   `softPlayerCount >= game.soft_max_players` **unless** the player is an admin and
   `admin.bypass_max_players` (default true) **or** the player was in the current round (`wasInGame`, so
   rejoining after a disconnect bypasses the cap). Deny reason `soft-player-cap-full` = "The server is full!",
   with the extra property `delay` = `game.server_full_reconnect_delay` (default **30** s).
5. Whitelist (non-admins). 6. IP intelligence (VPN/datacenter) checks.

A denial is sent as the Lidgren disconnect string, JSON-encoded by `Robust.Shared/Network/NetDisconnectMessage.cs`:
`{"reason":"The server is full!","redial":false,"delay":30}`. Lidgren may prefix `Disconnected: `; the client
strips it. `redial: true` tells the client to restart through the launcher (used for version mismatches).

No code was found that refuses a *fresh* connection attempt made before `delay` has elapsed; the delay only
disables the client's Retry button (**unverified** whether the engine rate-limits connection attempts
elsewhere).

## 6. Telling the launcher to connect

`SS14.Launcher/Program.cs`, `LauncherMessaging.cs`, `LauncherCommands.cs`, `ConfigConstants.cs`.

**Command line.** One argument that parses as an absolute URI (`SS14.Launcher ss14://host:1212`) becomes the
commands `r` (blank reason) and `c<uri>`. `--commands <cmd> [<cmd>...]` sends arbitrary commands (how the
client's redial works). Any other argument shape sends `:Ping` (activates the window).

**Commands** (one per line, UTF-8, no CR/LF inside):

| Command | Meaning |
|---|---|
| `:Ping` | activate the main window |
| `:RedialWait` | wait 1 s (`LauncherCommandsRedialWaitTimeout`) so a redialling client can die |
| `r<text>` / `R<hex of UTF-8 text>` | set the reason text shown under the connecting status |
| `c<uri>` / `C<hex of UTF-8 uri>` | connect to the server |

**Single instance over a named pipe.** Pipe name `SS14.Launcher.CommandPipe`; on Windows (and Linux without
`XDG_RUNTIME_DIR`) it is suffixed with `_` + uppercase hex of the UTF-8 user name (`Convert.ToHexString`), so
for user `jacob` it is `\\.\pipe\SS14.Launcher.CommandPipe_6A61636F62`. On Linux with `XDG_RUNTIME_DIR` the
pipe is the file `$XDG_RUNTIME_DIR/SS14.Launcher.CommandPipe`; on macOS the plain name. The pipe is created
with `CurrentUserOnly`, byte mode, one instance. A newly started launcher process first tries to connect to the
pipe with a **150 ms** timeout; on success it writes the commands joined by `\n` plus a trailing `\n`, prints
"Passed commands to primary launcher" and exits. Otherwise it becomes the primary launcher, creates the pipe
server, and queues its own commands for processing once the UI is up.

**What happens to a connect command** (`LauncherCommands.Connect`):

* waits (1 s polls) while there is no active account or its status is `Unsure`;
* drops it with `Dropping connect command: Account not available` if the account is not `Available`;
* drops it with `Dropping connect command: Busy connecting to a server` when `ConnectingVM != null`, i.e. the
  connecting overlay is open: during an attempt **and while an errored overlay waits to be dismissed**;
* otherwise activates the window, logs `Connect command: "<uri>", "<reason>"` and starts the connection.

## 7. The launcher's connect flow

`SS14.Launcher/Models/Connector.cs`, `ViewModels/ConnectingViewModel.cs`. Statuses in order:

`Connecting` (GET `/info`; any failure → `ConnectionFailed`, logged `Failed to connect: ConnectionFailed`) →
`AwaitingPrivacyPolicyAcceptance` (only when the server has one and it is new) → `Updating` (engine build,
modules, content; failure → `UpdateError`) → `StartingClient` → after **300 ms** with the client still alive →
`ClientRunning` → when the client exits → `ClientExited` (`ClientExitedBadly` when the exit code is not 0).

The overlay closes itself on `ClientRunning`, `Cancelled` and a clean `ClientExited`. It **stays open** on
`ConnectionFailed`, `UpdateError`, `NotAContentBundle` and a bad `ClientExited` until the user dismisses it,
and while open every further connect command is dropped (section 6). The launcher does not itself know
whether the game got into the server: it only tracks the process.

## 8. How the client is started

`Connector.ConnectLaunchClient` / `LaunchClient` / `GetLoaderStartInfo`. In release builds the launcher runs
`<launcher install dir>\loader\SS14.Loader.exe` (Linux: `loader/SS14.Loader`) with arguments

```
<engine zip path> <engine signature hex> <public key path>
--username <account name>
--cvar display.compat=<bool>
--cvar launch.launcher=true
--launcher                        (implies connect on start; the main menu is skipped)
--connect-address udp://host:port
--ss14-address ss14://host[:port]
--cvar build.download_url=... --cvar build.manifest_url=... --cvar build.manifest_download_url=...
--cvar build.version=... --cvar build.fork_id=... --cvar build.hash=... --cvar build.manifest_hash=...
--cvar build.engine_version=...
```

and environment `ROBUST_AUTH_TOKEN`, `ROBUST_AUTH_USERID`, `ROBUST_AUTH_PUBKEY`, `ROBUST_AUTH_SERVER`,
`SS14_LOADER_CONTENT_DB`, `SS14_LOADER_CONTENT_VERSION`, `SS14_LOADER_OVERLAY_ZIP`, `SS14_LAUNCHER_PATH`,
`DOTNET_TieredPGO=1`, `DOTNET_ReadyToRun=0`, `DOTNET_MULTILEVEL_LOOKUP=0`, optionally `DOTNET_gcServer=1`.
The client's stdout and stderr are redirected into `logs/client.stdout.log` and `logs/client.stderr.log`,
**recreated on every launch** (`FileMode.Create`). The launcher log records
`Setting up manual-pipe logging for new client with PID {pid}` right after the start, and the full
`Launch command: ...` at Debug level.

Replicating this outside the launcher would mean reimplementing login tokens, the content database and engine
signing. The tool drives the real launcher instead.

## 9. What the client does after launch

Content `Content.Client/Entry/EntryPoint.cs`, `Content.Client/Launcher/LauncherConnecting.cs`,
`LauncherConnectingGui.xaml.cs`; engine `Robust.Client/GameController/GameController.cs`,
`Robust.Shared/Network/NetManager.ClientConnect.cs`, `Robust.Client/BaseClient.cs`.

* With `--launcher` the client connects to `--connect-address` as soon as it has started
  (`GameController` calls `ConnectToServer` when `Launcher` or `Connect` is set). The content shows the
  `LauncherConnecting` state instead of the main menu, with pages `Connecting`, `ConnectFailed`,
  `Disconnected`.
* Connect sequence: resolve host → Lidgren connect ("happy eyeballs" over the resolved IPv4/IPv6 addresses)
  → engine handshake (auth, string table, serializer, transfer). A server denial arrives as a Lidgren status
  change to `Disconnected` with the JSON reason; the client raises `ConnectFailed` with the decoded reason and
  shows **"Failed to connect to server: The server is full!"**.
* On `ConnectFailed` the client **stays running**. The Retry button is disabled for `delay` seconds when the
  reason carries one (server full: 30 s by default), 15 s when the redial flag is set, then reads "Retry" /
  "Reconnect" / "Relaunch". Nothing is retried automatically; the process does not exit on its own. `Exit`
  calls `GameController.Shutdown`.
* A redial-flagged failure makes the client start the launcher executable (`SS14_LAUNCHER_PATH`) with
  `--commands :RedialWait R<hex reason> C<hex uri>` and shut itself down; a process redials at most once.
* After a successful join, a later disconnect switches to the `Disconnected` page with the reason and a
  Reconnect button, again without exiting.

## 10. Client log lines to detect the outcome

The engine's root log level is `Debug` (`Robust.Shared/Log/LogManager.cs`); the console handler writes
`[LEVL] sawmill: message` with levels `VERB`, `DEBG`, `INFO`, `WARN`, `ERRO`, `FATL`, and ANSI colours only
when stdout is a terminal (not when the launcher redirects it). The network sawmill is `net`. Lines in order
for one attempt (`NetManager.ClientConnect.cs`, `NetManager.cs`):

```
[DEBG] net: Attempting to connect to <host> port <port>
[DEBG] net: First attempt IP address is <ip>, second attempt <ip or null>
[DEBG] net: <endpoint>: Status changed to InitiatedConnect, reason: ...
[DEBG] net: <endpoint>: Status changed to Connected, reason: ...           # Lidgren-level connection accepted
[INFO] net: Client completed serializer handshake.
[INFO] net: Client completed transfer handshake.
[DEBG] net: Handshake completed, connection established.                  # joined
```

Failure signatures:

```
[DEBG] net: <endpoint>: Status changed to Disconnected, reason: Disconnected: {"reason":"The server is full!","redial":false,"delay":30}
[ERRO] net: Exception during handshake: ...                               # failure after the Lidgren connect
[INFO] net: <endpoint>: Disconnected (<reason>)                           # a later disconnect from an established connection
```

`launcher-ui` is the content's sawmill for redial messages. The exact Windows wording (message templates are
rendered with `{0}`-style and `{Name}`-style placeholders) is to be confirmed from a real `client.stdout.log`;
see `handoff.md`.

## 11. Windows install layout and data directories

`publish.py`, `SS14.Launcher.Bootstrap/Program.cs`, `LauncherPaths.cs`. The standalone Windows launcher is the
zip `SS14.Launcher_Windows.zip`, extracted anywhere:

```
Space Station 14 Launcher.exe   bootstrap: sets DOTNET_ROOT=<dir>\dotnet_x64 and starts bin_x64\SS14.Launcher.exe
                                WITHOUT forwarding its own arguments (so a URI given to it is lost)
bin_x64\SS14.Launcher.exe       the launcher (framework-dependent .NET 10; needs DOTNET_ROOT or a system runtime)
bin_x64\loader\SS14.Loader.exe  the game client process
dotnet_x64\                     bundled .NET runtime
console.bat                     runs the launcher with a console
```

The standalone launcher registers **no** `ss14://` URL protocol on Windows (the only registry access is a
Wine check and a `DOTNET_ROOT` cleanup). The Linux desktop entry passes `%u` but declares no scheme handler.
The Steam build is separate, private code and out of scope.

| Data | Windows | Linux |
|---|---|---|
| user data (`logs\`, `engines\`, `modules\`) | `%APPDATA%\Space Station 14\launcher\` | `~/.local/share/Space Station 14/launcher/` |
| local data (`content.db`, `override_assets.db`) | `%LOCALAPPDATA%\Space Station 14\launcher\` | same as user data |
| launcher log | `logs\launcher-YYYYMMDD.log` (Serilog, daily, 7 kept, Debug level; `LogLauncherVerbose` cvar for Verbose) | same |
| client logs | `logs\client.stdout.log`, `logs\client.stderr.log` | same |

`SS14_LAUNCHER_APPDATA_NAME` replaces the `launcher` folder name (for a second, independent launcher profile).

Useful launcher log lines: `Connect command: "<uri>", "<reason>"`, `Dropping connect command: ...`,
`Failed to connect: <Status>`, `Launch command: <exe> [0] <arg> [1] ...`,
`Setting up manual-pipe logging for new client with PID <pid>`, `Passed commands to primary launcher` and
`We are primary launcher (or primary launcher is out for lunch)` (the last two go to the console only).

## 12. Timing constants

| What | Value | Where |
|---|---|---|
| status request timeout | 5 s | `ConfigConstants.ServerStatusTimeout` |
| pipe connect timeout of a second launcher instance | 150 ms | `LauncherCommandsNamedPipeTimeout` |
| `:RedialWait` | 1 s | `LauncherCommandsRedialWaitTimeout` |
| client considered crashed if it exits within | 300 ms | `Connector.LaunchClientWrap` |
| server-full retry delay shown to the player | 30 s (server cvar) | `game.server_full_reconnect_delay` |
| redial-flag retry delay | 15 s | `LauncherConnectingGui.RedialWaitTimeSeconds` |
| soft cap default | 30 | `game.soft_max_players` |

## 13. Not verified, and to check on Windows

* Whether `players` in `/status` counts players still in the handshake (it uses `PlayerCount`, which counts
  sessions; sessions are created at approval time, so probably yes, but not read).
* Any engine-side rate limit on repeated connection attempts from one address.
* The exact wording of the log lines on Windows and whether `client.stdout.log` is flushed promptly enough to
  tail (the launcher pipes with a 4 KiB async `FileStream`).
* Whether `PipeOptions.CurrentUserOnly` accepts a Python client on the same user account (it should; the
  fallback of invoking `bin_x64\SS14.Launcher.exe <uri>` avoids the question).
