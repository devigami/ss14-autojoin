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

## Checked off the reference machine

These are real runs, but not on the reference Windows machine: the cloud development container (Linux) and
GitHub's hosted runners. They say that a build starts and what it prints, nothing about joining.

| Date | Where | Check | Result |
|---|---|---|---|
| 2026-11-21 | Linux container | Window and console builds with uv's Python 3.14.6, PyInstaller 6.22.3 (the pinned version, unchanged since 1.0.0) | Built without error, but the window build died on start: `ImportError: libtcl9.0.so`. In 3.14.6 `_tkinter` needs `libtcl9.0.so` and `libtcl9tk9.0.so` and has no RPATH, so `ldd` reports them "not found"; PyInstaller logs `Library not found` as a warning and leaves them out. |
| 2026-11-21 | Linux container | Same builds with `build.tcl_tk_libraries` adding the two files | `tools/smoke_version.py`: `SS14 Auto-Join 1.0.0` and `ss14-autojoin 1.0.0`, exit 0. Under Xvfb the window opens from both builds (`SS14AutoJoin`, `ss14-autojoin gui`) and draws the settings panel; `timeout 10` ends it with status 124. A build without the fix exits 1 in the same check. |
| 2026-11-21 | Linux container | Published `SS14AutoJoin-1.0.0-linux-x64` (checksum matches `SHA256SUMS.txt`) | Starts and stays open under Xvfb. Its bundle holds both Tcl/Tk libraries: it was built with Python 3.14.7, whose `_tkinter` has `RPATH $ORIGIN/../..` (read from the extension extracted from the bundle), so PyInstaller found them. The release was never affected; the container's older uv installs 3.14.6. |
| 2026-11-21 | GitHub Windows runner (windows-2025, Python 3.14.10), commit `4262fca` | Window build asked for `--version` four ways | Captured through a pipe by `tools/smoke_version.py`: `SS14 Auto-Join 1.0.0`, exit 0. PowerShell `... \| Out-String` and `cmd /c "... \| more"`: the version. PowerShell `$v = .\dist\SS14AutoJoin.exe --version`: empty, returned in 0.2 s, because PowerShell does not wait for a windowed program that is last in its pipeline; the abandoned process then logged `Exception ignored while flushing sys.stdout: OSError: [Errno 22] Invalid argument`. |
| 2026-11-21 | Same runner, commit `9a8dc5b` (the line now goes straight to the file descriptor) | Same checks, plus a run with a pipe nobody reads | `nobody listening: exit 0, error stream ''`; the piped PowerShell and Command Prompt forms print `SS14 Auto-Join 1.0.0`; the Windows-only tests of the real standard-output-handle route and the stopped-listening test pass. |
| 2026-11-21 | GitHub Linux runner (ubuntu-26.04, Python 3.14.10), commit `9a8dc5b` | Builds, smoke check, window on a virtual display | No `Library not found` warning: this Python's `_tkinter` is resolvable, so the runner never had the container's defect. Smoke check passes; the window stays open until `timeout` ends it (status 124). |

## Not verified

* Linux and macOS joining (the console build runs on Linux; the launcher path is the same in source).
* The standalone (non-Steam) launcher edition.
* Whether Steam must be running for the Steam launcher to cold-start (it was running in the test).
* Servers with a whitelist or the panic bunker enabled (the deny reasons are handled from the source, not
  from a real log).
* `winget install Devigami.SS14AutoJoin` from the community source, and that the installed `SS14AutoJoin`
  starts without a SmartScreen prompt (expected from the winget client source, see
  `packaging/winget/README.md`; the earlier local test used `--manifest`, which takes a different path).
* `SS14AutoJoin --version` typed into PowerShell and into Command Prompt on a real desktop, with nothing
  piped: this is the parent-console route of `console.py`, which no test can observe. Expected: the prompt
  returns first, then `SS14 Auto-Join <version>` on its own line. Also that the title bar shows the version.
