# Fixtures

Real files from Jacob's machine that the tool's parsers are tested against. Redact user ids, tokens and other
players' names before committing. Expected files (see `docs/handoff.md`):

* `client.stdout.full.log`: the game client's stdout after "The server is full!".
* `client.stdout.joined.log`: the same for a successful join, up to the first minute in game.
* `launcher.full.log`: the launcher log lines of a failed attempt.
