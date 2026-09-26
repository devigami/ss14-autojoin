# How it works

The tool is a loop with four states. Everything it knows about the launcher and the game engine was read
from their open-source code and checked against real logs; the details are in the
[development reference](development/launcher-reference.md).

```
 watch ──────────────▶ connect ──────────────▶ verify ──────────────▶ joined
 GET /status every     run the launcher with     watch the client's       fanfare, stop
 few seconds until     the server address;       UDP socket and log       (or keep watching
 players < max         pick up the client PID    for ~15 s                 with "rejoin")
       ▲               from the launcher log            │
       │                                                │ rejected / no socket
       └──────── close the client, read the reason, wait 2 s ◀──┘
```

## Watching

Every SS14 server publishes a small status page (the launcher uses the same one to draw its server list).
It contains the current player count and the soft player cap. The tool fetches it every three seconds
(configurable, never faster than once a second) and waits until `players < cap`, optionally with a margin of
extra free slots. If the server is unreachable it backs off to ten seconds.

## Connecting

The only supported way to start the game is through the official launcher, which holds your login token, the
downloaded content and the engine signature. The tool runs the launcher executable with the server address
as its argument, the same mechanism the launcher itself uses for `ss14://` links. If the launcher is already
running, the request is forwarded to it; if not, the launcher starts, logs in and connects by itself.

The launcher writes a log line with the game client's process ID when it starts the client. The tool picks
that up within a second or two.

## Verifying

Whether the join succeeded is not something the launcher knows, and the game client does not exit when the
server rejects it: it sits on a "Failed to connect" screen with a retry timer. The tool uses two witnesses:

* **The client's network sockets.** A connected client keeps one UDP socket open for the whole session. A
  rejected client closes its sockets within a couple of seconds. A socket held open for fifteen seconds is
  counted as a join; no socket after twelve seconds as a rejection.
* **The client log.** The launcher captures the game's output to `client.stdout.log`, but it only writes that
  file in 4 KiB chunks, so while the client is quiet the log lags. When it does flush, the handshake lines
  give an early answer, and after a rejected client is closed the log always contains the server's reason
  (for example `The server is full!`).

If neither witness has spoken by the timeout (60 s by default), the tool assumes nothing. By default it
leaves the client running and stops, so a live session is never killed on a guess. You can switch that to
"close it and retry".

## Retrying

After a rejection the tool closes the game client (only ever the game loader process it started), waits for
the log to flush, reads the reason, pauses two seconds and watches again. It keeps count: if the reason is
not a full server (a ban, a whitelist, the panic bunker), it stops, because retrying would not help. If it
cannot read any reason several times in a row, it also stops rather than loop blindly.

## Fairness

The tool does nothing a player cannot do by hand. It waits for the public status page to show a free slot,
then presses Connect once. It cannot reserve a slot, skip the queue or bypass any server rule.
