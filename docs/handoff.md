# Hand-off: steps that need Jacob or Windows

Each item says what to run, what to look for, and what result means success. Paste results (logs, paths) into
the repository (`docs/fixtures/`) or the session, and tick the item. Nothing else on this page is needed.

## Now (unblocks M2)

1. **Launcher install path.** Find the folder that holds `Space Station 14 Launcher.exe`, `bin_x64\` and
   `dotnet_x64\` (the standalone launcher zip's contents). Record the full path in `docs/decisions.md` or pass
   it to the tool with `--launcher <path>`. If the launcher was installed through Steam instead, stop and say
   so: the Steam build is different code and the plan needs a new look.
2. **Connect by command line.** With the launcher running and logged in, in PowerShell:

   ```powershell
   $env:DOTNET_ROOT = "<install>\dotnet_x64"
   & "<install>\bin_x64\SS14.Launcher.exe" "ss14://<target server>"
   ```

   Success: the console prints `Passed commands to primary launcher`, the launcher window comes to the front
   and starts connecting. Then quit the launcher and run the same command again: it should start the launcher
   and connect once the account is logged in. Note anything different.
3. ~~Capture a failed attempt~~ **Done 2026-09-25**, twice: `client.stdout.full.log` (copied while the client
   was open, truncated by the launcher's buffer) and `client.stdout.full-after-exit.log` (complete, with the
   denial). Still wanted from one attempt: the day's `launcher-YYYYMMDD.log` lines, as `docs/fixtures/launcher.full.log`.
4. ~~Capture a successful attempt~~ **Done 2026-09-25** (`docs/fixtures/client.stdout.joined.log`).
5. **Target server.** The `ss14://` address (or the exact server name as the launcher shows it) of the server
   to auto-join, and whether it runs a whitelist or panic bunker.

## Later (M2, M3)

6. Run `uv run ss14-autojoin doctor` on Windows and paste the output (detected paths, pipe name, log files).
7. First end-to-end run: `uv run ss14-autojoin join ss14://<server>` while the server is full. Success: the
   tool logs each poll, launches when a slot appears, and either reports "joined" or cleans up and resumes.
   Paste the tool's log.
8. Named pipe test (optional optimisation): `uv run ss14-autojoin doctor --pipe-test` when it exists. Success:
   the launcher window activates (`:Ping`).
9. Build the Windows binary with `uv run python build.py` if CI's `windows-latest` job is not used, and run
   the `--onefile` exe once for each CLI mode.
