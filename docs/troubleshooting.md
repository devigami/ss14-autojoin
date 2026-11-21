# Troubleshooting

When something goes wrong, the log in the window (or the console output) is the first thing to read, and the
thing to attach to an [issue](https://github.com/devigami/ss14-autojoin/issues/new/choose). `ss14-autojoin doctor`
adds what the tool found on your machine.

## "Launcher installation not found"

The tool looks for the folder that contains `bin_x64\SS14.Launcher.exe`. It checks a running launcher, the
launcher's log, every Steam library and the usual places for the standalone zip. If it still cannot find it,
press **Browse…** and pick the folder yourself: for Steam, `…\steamapps\common\Space Station 14 Playtest` or
`…\steamapps\common\Space Station 14`; for the standalone launcher, wherever you extracted the zip (the folder
with `Space Station 14 Launcher.exe`, `bin_x64` and `dotnet_x64`).

## It launched the game but reported "no join" and left the client running

That is the safe default when neither witness could decide (see [How it works](how-it-works.md)). Look at the
game window: if you are in, all is well. If it shows "Failed to connect", close it and start watching again,
or set **If unsure after the timeout** to `retry`. Please report the log, since this should be rare.

## It keeps stopping with "the server refused the connection"

The server gave a reason other than being full: a ban, a whitelist, or the panic bunker. Retrying would not
help, so the tool stops. The reason is printed in the log.

## "the launcher is showing an error and drops connect commands"

The launcher's own connecting dialog ended in an error (for example it could not reach the server's info
page) and stays open; while it does, the launcher ignores new connect requests. Dismiss the dialog in the
launcher, or turn on **Restart a stuck launcher**.

## The player count never drops below the cap

Popular servers hover exactly at the cap for long stretches. The count you see is the server's own; the tool
attempts as soon as it dips. If several people compete, try **Extra free slots** at 0 (the default) and a
shorter **Poll every** of 1 or 2 seconds.

## No sound

Check **Play a fanfare when joined**. `ss14-autojoin doctor` prints the `join sound:` path; if it says
missing, the build is incomplete. The fanfare uses the Windows sound API; on other systems it needs
`afplay`, `paplay` or `aplay`.

## Windows says the executable is unrecognised

The builds are not code-signed, so Windows shows "Windows protected your PC" for a copy downloaded with a
browser. Three ways past it:

* Install with `winget install Devigami.SS14AutoJoin` instead. winget verifies the file against the hash in
  the reviewed package manifest and Windows does not prompt for a program installed that way.
* Choose **More info** and **Run anyway**, after checking the download against `SHA256SUMS.txt` on the release
  (`Get-FileHash .\SS14AutoJoin-<version>-windows-x64.exe` in PowerShell).
* Build it yourself from source with `uv run python build.py`.

## `SS14AutoJoin` is not recognised after a winget install

winget puts the command in its own links folder and adds that folder to your `PATH`, which terminals read
when they start. Open a new terminal window. `winget list Devigami.SS14AutoJoin` confirms the install.

## `SS14AutoJoin --version` prints late, or nothing

That is how Windows treats a windowed program started from a terminal: the shell does not wait for it. Pipe
the output (`SS14AutoJoin --version | Out-Host`, or `| Out-String` to capture it; a plain
`$v = SS14AutoJoin --version` stays empty) or read the version from the title bar. Versions before 1.0.1
ignore the flag and open the window. Details in [Command line](command-line.md#which-version).

## The icon looks wrong in Explorer

Windows caches icons by path. If you rebuilt the executable in place, copy it to a new folder or run
`ie4uinit.exe -show` to refresh the cache.

## Reporting a problem

Please include:

1. The tool's log (window or console), from the start of the run.
2. `ss14-autojoin doctor` output.
3. Whether the launcher is the Steam or standalone edition, and your Windows version.
4. If the game client was involved: `%APPDATA%\Space Station 14\launcher\logs\client.stdout.log` after closing
   the client, and the relevant lines of `launcher-YYYYMMDD.log` from the same folder. Remove your account
   name if you prefer; the tool never needs it.
