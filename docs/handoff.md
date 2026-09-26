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
7. ~~End-to-end run~~ **Done 2026-09-26 10:35**: slot at 78/80, connect, client PID after 2 s, join confirmed
   from the UDP socket after 15 s, client left running. Exit code 0.
8. Named pipe test (optional optimisation): `uv run ss14-autojoin doctor --pipe-test` when it exists. Success:
   the launcher window activates (`:Ping`).
9. **The window (M3).** `git pull`, `uv sync --all-groups`, then `uv run ss14-autojoin gui`. Expected: the
   launcher folder is pre-filled from detection, the server defaults to Lizard; press **Start watching** and
   it behaves like the console `join` with the log in the window; **Stop** ends it; **Save settings** writes
   `%APPDATA%\ss14-autojoin\config.toml`. Say what looks wrong or is missing (sizes, labels, a field you
   want).
10. **The executable.** Either download the `SS14AutoJoin-windows` artifact from the CI run of the latest
    push (GitHub → Actions → the run → Artifacts) or build locally with `uv run python build.py` (window) and
    `uv run python build.py --cli` (console) into `dist\`. Run `SS14AutoJoin.exe` once: same window as item 9.
    Windows Defender may want a moment with an unsigned one-file exe.
