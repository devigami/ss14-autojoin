# Command line

The console executable `ss14-autojoin.exe` (or `uv run ss14-autojoin` from source) offers the same loop as the
window plus a few diagnostic commands. Every command prints `--help`.

| Command | What it does |
|---|---|
| `ss14-autojoin status <address>` | Fetch the server's status once: name, players, cap, round state. `--json` prints the raw status. |
| `ss14-autojoin watch <address>` | Poll the status and print a line whenever the player count or slot state changes. No connecting. |
| `ss14-autojoin join <address>` | The auto-join loop. Flags mirror the [settings](settings.md): `--launcher`, `--interval`, `--margin`, `--attempt-timeout`, `--on-unknown keep|retry`, `--cooldown`, `--max-attempts`, `--rejoin`, `--restart-launcher`, `--skip-panic-bunker`, `--quiet`, `--verbose`. |
| `ss14-autojoin doctor` | Show what the tool found: launcher install and how it was found, loader executable, bundled .NET runtime, log folders, join sound. Attach this to bug reports. |
| `ss14-autojoin probe` | Sample a running game client's UDP sockets for a few seconds (1 = connected, 0 = rejected). |
| `ss14-autojoin gui` | Open the window. |

Exit codes: `0` success (joined), `1` not joined or unreachable, `2` bad arguments, `130` interrupted.

## Which version

```powershell
ss14-autojoin --version     # the console tool: ss14-autojoin 1.0.1
SS14AutoJoin --version      # the window program, from 1.0.1: SS14 Auto-Join 1.0.1
```

The window program prints its version and exits without opening the window. It is a windowed program, and
Windows gives those no console of their own, which has two visible effects when you type the command into a
terminal: the shell does not wait for it, so the prompt comes back first and the version appears on the line
after it; and nothing is printed at all when it is started from a shortcut. Piping makes the shell wait and
puts the output where you expect it:

```powershell
SS14AutoJoin --version | Out-Host          # PowerShell
$version = SS14AutoJoin --version          # PowerShell, captured into a variable
```

```bat
SS14AutoJoin --version | more
```

The title bar of the window shows the same version.

## Example

```powershell
ss14-autojoin join ss14s://lizard.spacestation14.io/server --verbose --max-attempts 5
```

```
launcher: C:\...\Space Station 14 Playtest\bin_x64\SS14.Launcher.exe (steam, via running launcher)
logs:     C:\Users\you\AppData\Roaming\Space Station 14\launcher\logs
watching ss14s://lizard.spacestation14.io/server via https://lizard.spacestation14.io/server/status (Ctrl+C to stop)
[10:42:52] status   77/80 players, slot free
[10:42:52] attempt  attempt 1: asking the launcher to connect to ss14s://lizard.spacestation14.io/server
[10:42:54] status   client started (pid 32736), waiting for the join
[10:43:09] joined   joined ss14s://lizard.spacestation14.io/server on attempt 1 (client kept a UDP socket open for 15 s)
[10:43:09] stop     joined on attempt 1
```
