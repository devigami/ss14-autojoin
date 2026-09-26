# Fixtures

Real log files from the reference Windows machine (Steam launcher 0.40.1.0, Robust 290.0.0) that the tool's parsers are tested against. Player names are replaced
(`PLAYER_NAME`, `OTHER_PLAYER`, `CHARACTER`), chat text and the 12 KB OpenGL extension list are removed;
everything else is verbatim.

* `client.stdout.joined.log` (2026-09-25): a successful join to `lizard.spacestation14.com`, launcher on
  Robust 290.0.0, up to the first minutes in game. The join is visible as `Status changed to Connected`,
  `Handshake completed, connection established.`, the three handshake `INFO` lines, `Runlevel changed to:
  Connected` and `InGame`.
* `client.stdout.full.log` (2026-09-25): copied **while the client was showing "The server is full!"**. The
  file ends at `Switching to state Content.Client.Launcher.LauncherConnecting`: the connect and failure lines
  were still sitting in the launcher's unflushed 4 KiB write buffer (`Connector.PipeOutput`). This is the
  evidence that the log cannot be tailed in real time for failures; see the reference, section 10.

* `client.stdout.full-after-exit.log` (2026-09-25): a second "server is full" attempt, copied **after** pressing
  Exit in the client. The buffer was flushed on exit: the denial arrives during the handshake as a Lidgren
  `Disconnected` with the JSON reason `Connect denied: The server is full!` (delay 30), followed by
  `Runlevel changed to: Initialize` and `[ERRO] net: Exception during handshake: ...ClientDisconnectedException`.

* `launcher.log` (2026-09-26, launcher 0.40.1.0, **Steam build**): the launcher's own log around the successful
  join (client PID 7136, 08:45 to 09:04) and the failed one (PID 26840, 09:05:27 to 09:06:28). Trimmed of repeated
  hub and favourite refresh lines and of the migration noise; account id replaced with zeros. Extended 2026-09-26
  with two command-line connects: one with the launcher running (09:22, forwarded over the pipe, `Launcher
  command: r` / `css14s://...` then `Connect command:`), one with the launcher closed (09:34: the launcher
  starts, queues the commands, logs in, then connects; client PID 17572 launched 5.7 s after start).
