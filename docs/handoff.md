# Hand-off: steps that need Jacob or Windows

Each item says what to run, what to look for, and what result means success. Paste results (logs, paths) into
the repository (`docs/fixtures/`) or the session, and tick the item. Nothing else on this page is needed.

## Now (unblocks M2)

1. ~~Launcher install path~~ **Known from the launcher log (2026-09-26)**:
   `D:\SteamLibrary\steamapps\common\Space Station 14 Playtest\` (Steam build 0.40.1.0). Please confirm it
   contains `bin_x64\SS14.Launcher.exe` and a `dotnet_x64\` folder (`dir` of that folder is enough).
2. ~~Connect by command line~~ **Done 2026-09-26: works on the Steam build** (client launched and got the
   server-full denial). Two small follow-ups: (a) paste a `dir` of
   `D:\SteamLibrary\steamapps\common\Space Station 14 Playtest` (which `dotnet_*` and `bin_*` folders exist);
   (b) with the launcher **closed** and Steam running, run the same command once more: does the launcher start
   and connect by itself? Note whether Steam shows the game as running.
3. ~~Capture a failed attempt~~ **Done 2026-09-25**, twice: `client.stdout.full.log` (copied while the client
   was open, truncated by the launcher's buffer) and `client.stdout.full-after-exit.log` (complete, with the
   denial). Launcher log received too (`docs/fixtures/launcher.log`).
4. ~~Capture a successful attempt~~ **Done 2026-09-25** (`docs/fixtures/client.stdout.joined.log`).
5. ~~Target server~~ **Lizard, `ss14s://lizard.spacestation14.io/server`** (from the launcher log). Say if it
   should be Leviathan or another server instead, and whether the target runs a whitelist or panic bunker.

## Later (M2, M3)

6. Run `uv run ss14-autojoin doctor` on Windows and paste the output (it exists now: detected install, runtime folder, log paths).
7. First end-to-end run: `uv run ss14-autojoin join ss14://<server>` while the server is full. Success: the
   tool logs each poll, launches when a slot appears, and either reports "joined" or cleans up and resumes.
   Paste the tool's log.
8. Named pipe test (optional optimisation): `uv run ss14-autojoin doctor --pipe-test` when it exists. Success:
   the launcher window activates (`:Ping`).
9. Build the Windows binary with `uv run python build.py` if CI's `windows-latest` job is not used, and run
   the `--onefile` exe once for each CLI mode.
