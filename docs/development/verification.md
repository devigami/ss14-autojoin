# Verification record

What "verified" means in the other development documents: each item below was checked on the reference
Windows machine (Windows 11 24H2, Steam edition of the launcher 0.40.1.0, Robust 290.0.0, content fork
`wizards-testing`), on the dates given. Logs from these checks are the fixtures under `fixtures/`, redacted.
Anything not listed here is untested; the issue templates ask users for exactly these artefacts.

## Launcher and installation

| Date | Check | Result |
|---|---|---|
| 2026-09-26 | Install layout of the Steam edition | `<Steam library>\steamapps\common\Space Station 14 Playtest\` holds `bin_x64\SS14.Launcher.exe`, `bin_x64\loader\SS14.Loader.exe`, `bin_x64\signing_key`, `dotnet_x64\`, `console.bat`, `Space Station 14 Launcher.exe`, plus a leftover `bin\` from 2025. Same layout as the standalone zip. |
| 2026-09-26 | `bin_x64\SS14.Launcher.exe <ss14 uri>` with the launcher **running** | Forwarded over the named pipe: launcher log shows `Launcher command: r`, `Launcher command: c<uri>`, `Connect command:` 2 ms later, `Launch command` 3.2 s later. Client started and attempted the join. |
| 2026-09-26 | Same command with the launcher **closed** (Steam running) | The new process became the launcher, queued the commands, refreshed the token, connected: `Connect command` at +2.7 s, client PID at +5.7 s. |
| 2026-09-26 | `ss14-autojoin doctor` | Found the install via the running launcher, the loader, `dotnet_x64`, the data and log folders, the join sound. |

## Detecting the outcome

| Date | Check | Result |
|---|---|---|
| 2026-09-25 | `client.stdout.log` after a successful join | Complete; the join markers (`Status changed to Connected`, `Handshake completed`, handshake `INFO` lines, `Runlevel changed to: Connected`/`InGame`) match the engine source. Fixture `client.stdout.joined.log`. |
| 2026-09-25 | `client.stdout.log` copied **while** a rejected client was showing "The server is full!" | Truncated before any `net:` line: the launcher's 4 KiB write buffer had not flushed. Fixture `client.stdout.full.log`. |
| 2026-09-25 | Same log copied **after** pressing Exit in the rejected client | Complete: the denial arrives during the handshake as `Status changed to Disconnected, reason: "{\"reason\":\"Connect denied: The server is full!\",\"redial\":false,\"delay\":30}"`, then `Runlevel changed to: Initialize` and `Exception during handshake`. Fixture `client.stdout.full-after-exit.log`. |
| 2026-09-26 | First `join` run (45 s log-based timeout) | Slot detection, connect, PID pick-up and termination worked, but a client that had joined and was waiting in the lobby was killed: its log never flushed either. Led to the socket witness and the keep-on-unknown default. |
| 2026-09-26 | `ss14-autojoin probe` on a connected client and on a rejected one | `udp_sockets=1` every second while connected, `udp_sockets=0` on the failure screen. No elevation needed. |
| 2026-09-26 | Second `join` run | `78/80 slot free` → connect → PID after 2 s → `joined (client kept a UDP socket open for 15 s)` → stop, game left running. Exit code 0. |

## Window, build and extras

| Date | Check | Result |
|---|---|---|
| 2026-09-26 | `ss14-autojoin gui` | Launcher folder pre-filled from detection; Save wrote `%APPDATA%\ss14-autojoin\config.toml`; Start joined Lizard through the window (77/80, PID after 2 s, joined at 15 s). |
| 2026-09-26 | PyInstaller window build (`build.py`) | `SS14AutoJoin.exe` runs, same behaviour as from source; the fanfare plays from the bundled data; the setting switch is respected. |
| 2026-09-26 | Icon | Explorer showed the icon once the exe was copied to a path without a cached entry; the taskbar shows it from the exe resource; the title bar needed the `WM_SETICON` fallback because Tk 9.0.4's `iconbitmap` did nothing on Windows. Log: `icon set (ico) ... with Tk 9.0.4`, `icon applied through the Windows API`. |

## Not verified

* Linux and macOS joining (the console build runs on Linux; the launcher path is the same in source).
* The standalone (non-Steam) launcher edition.
* Whether Steam must be running for the Steam launcher to cold-start (it was running in the test).
* Servers with a whitelist or the panic bunker enabled (the deny reasons are handled from the source, not
  from a real log).
