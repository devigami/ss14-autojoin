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
7. **First end-to-end run (ready to try).** In the repository folder on Windows:

   ```powershell
   uv sync --all-groups
   uv run ss14-autojoin doctor
   uv run ss14-autojoin join ss14s://lizard.spacestation14.io/server --verbose
   ```

   The tool polls Lizard every 3 s, prints a line when the player count or slot state changes, and when a slot
   is free runs `bin_x64\SS14.Launcher.exe <uri>`. It then waits for the client PID in the launcher log, reads
   `client.stdout.log` for the join, and on a "server is full" denial (or 45 s without a join) closes the
   client with `terminate`, reads the reason once the log flushes, waits 2 s and watches again. Success is a
   `joined` line and exit code 0. Paste the whole console output, joined or not; the interesting cases are a
   wrong PID, a client left open, or an attempt that never sees the join although you are in the game.
   Useful flags: `--max-attempts 3` for a bounded test, `--rejoin`, `--restart-launcher`.
8. Named pipe test (optional optimisation): `uv run ss14-autojoin doctor --pipe-test` when it exists. Success:
   the launcher window activates (`:Ping`).
9. Build the Windows binary with `uv run python build.py` if CI's `windows-latest` job is not used, and run
   the `--onefile` exe once for each CLI mode.
