# Settings

All settings live in the window and in `%APPDATA%\ss14-autojoin\config.toml` (a plain text file you can edit;
`SS14_AUTOJOIN_CONFIG` overrides the location). Command-line flags take precedence over the file.

| Setting | File key | Default | What it does |
|---|---|---|---|
| Game / launcher folder | `launcher_dir` | auto-detect | The folder that contains `bin_x64` (the launcher install). Empty means detect: a running launcher, the launcher log, Steam libraries, common standalone locations. |
| Server address | `server` | Wizard's Den Lizard | `ss14://host[:port]` or `ss14s://host/path`. The scheme may be left off; the port defaults to 1212. |
| Poll every (s) | `interval` | 3 | Seconds between status checks while watching. Minimum 1. |
| Extra free slots | `margin` | 0 | Only attempt when there are this many free slots beyond one. Useful on servers where several people race for each slot. |
| Decide after (s) | `attempt_timeout` | 60 | Seconds after the game client starts until the attempt must be decided. |
| Cooldown (s) | `cooldown` | 2 | Pause after a rejected attempt before watching again. |
| Max attempts | `max_attempts` | 0 (unlimited) | Stop after this many attempts. |
| Rejoin | `rejoin` | off | After a join, keep an eye on the game; when it exits or is disconnected, start watching again. |
| Restart a stuck launcher | `restart_launcher` | off | If the launcher is showing an error dialog it silently ignores connect requests. With this on, the tool restarts the launcher with the server address. |
| Skip while panic bunker is on | `skip_panic_bunker` | off | Do not attempt while the server reports its panic bunker enabled (new accounts would be refused anyway). |
| If unsure after the timeout | `on_unknown` | `keep` | `keep`: leave the game running and stop the tool. `retry`: close the client and try again. |
| Play a fanfare when joined | `sound` | on | A short brass "ta-da" when the join lands. |

## Choosing a server address

The launcher stores each server by its `ss14://` address. Official Wizard's Den servers use `ss14s://`
addresses with a path, for example `ss14s://lizard.spacestation14.io/server`. Community servers usually
advertise `ss14://their.host` (port 1212 implied) on their website or Discord. You can check an address with
the console tool: `ss14-autojoin status ss14://their.host` prints the server name and player count.

## Example configuration file

```toml
# ss14-autojoin settings. Edited by the app; hand edits are fine.
launcher_dir = "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Space Station 14 Playtest"
server = "ss14s://lizard.spacestation14.io/server"
interval = 3.0
margin = 0
attempt_timeout = 60.0
on_unknown = "keep"
cooldown = 2.0
max_attempts = 0
rejoin = false
restart_launcher = false
skip_panic_bunker = false
sound = true
```
