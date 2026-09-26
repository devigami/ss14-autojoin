# Hand-off: steps that need Jacob or Windows

Each item says what to run, what to look for, and what result means success. Paste results (logs, paths) into
the repository (`docs/fixtures/`) or the session, and tick the item. Nothing else on this page is needed.

## Now (unblocks M2)

1. ~~Launcher install path~~ **Known from the launcher log (2026-09-26)**:
   `D:\SteamLibrary\steamapps\common\Space Station 14 Playtest\` (Steam build 0.40.1.0). Please confirm it
   contains `bin_x64\SS14.Launcher.exe` and a `dotnet_x64\` folder (`dir` of that folder is enough).
2. ~~Connect by command line~~ **Done 2026-09-26, both with the launcher running and with it closed** (the
   launcher starts, logs in and connects by itself). `dir` shows `bin`, `bin_x64`, `dotnet_x64`, `console.bat`,
   `Space Station 14 Launcher.exe`.
3. ~~Capture a failed attempt~~ **Done 2026-09-25**, twice: `client.stdout.full.log` (copied while the client
   was open, truncated by the launcher's buffer) and `client.stdout.full-after-exit.log` (complete, with the
   denial). Launcher log received too (`docs/fixtures/launcher.log`).
4. ~~Capture a successful attempt~~ **Done 2026-09-25** (`docs/fixtures/client.stdout.joined.log`).
5. ~~Target server~~ **Lizard, `ss14s://lizard.spacestation14.io/server`** (from the launcher log). Say if it
   should be Leviathan or another server instead, and whether the target runs a whitelist or panic bunker.

## Later (M2, M3)

6. Run `uv run ss14-autojoin doctor` on Windows and paste the output (it exists now: detected install, runtime folder, log paths).
7. **End-to-end run, second try.** The first run (2026-09-26 10:03) found slots and launched correctly but
   killed a client that had joined, because the client log never flushed. Two checks now:

   (a) **Does psutil see the client's UDP socket?** With the game running and connected (any server), then
   again while it shows "Failed to connect":

   ```powershell
   uv run ss14-autojoin probe --seconds 5
   ```

   Expected: `udp_sockets=1` (or more) while connected, `udp_sockets=0` on the failure screen. If it prints
   `udp_sockets=None` in both cases, Windows is not letting the tool read the socket table and the fallback
   is the keep-on-unknown behaviour only; say so.

   (b) **The loop again**, when Lizard is near full:

   ```powershell
   uv run ss14-autojoin join ss14s://lizard.spacestation14.io/server --verbose --max-attempts 3
   ```

   Now a join is reported after about 15 s from the socket, a rejection after about 12 s, and if neither can be
   seen the tool stops and leaves the client running with a message naming its PID (it never closes a client
   without evidence). Paste the console output.
8. Named pipe test (optional optimisation): `uv run ss14-autojoin doctor --pipe-test` when it exists. Success:
   the launcher window activates (`:Ping`).
9. Build the Windows binary with `uv run python build.py` if CI's `windows-latest` job is not used, and run
   the `--onefile` exe once for each CLI mode.
