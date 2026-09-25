# Fixtures

Real files from Jacob's machine that the tool's parsers are tested against. Player names are replaced
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

Still wanted: the same `client.stdout.log` **after** the failed client has been closed (does the buffer get
flushed on exit?), and the launcher log lines of one attempt (`launcher.full.log`).
