# FAQ

**Is this cheating or against server rules?**
It does what you would do by hand: watch the player count and press Connect when a slot is free, one attempt
per slot. It cannot reserve a slot or bypass the server's rules; a full server rejects it exactly as it
would reject you. Servers that dislike automated rejoining may say so in their rules, so read them.

**Does it need my Space Station 14 account?**
No. Login stays inside the official launcher. The tool only tells the launcher which server to connect to
and watches whether the game got in.

**Which launcher editions work?**
The Steam edition is verified. The standalone launcher has the same layout and the same command handling in
its source, so it is expected to work; reports welcome.

**Does it work on Linux or macOS?**
The code runs and the console build works on Linux, but joining has only been tested on Windows. The
launcher's command-line interface is the same on all platforms, so it may well work. If you try it, please
share what happened in an issue.

**How fast is it?**
From a free slot appearing on the status page to a confirmed join takes about 17 seconds: 2 s for the
launcher to start the client and 15 s of watching the client's network socket before declaring success.
The connection itself is made within the first few seconds; the wait is confirmation.

**Will it kill my game?**
Only a client it started, and only when the server rejected it or (if you choose `retry`) when nothing
could be decided. When in doubt it leaves the game alone and stops.

**Can I watch two servers?**
Not in one window. Run two copies of the console tool with different addresses if you must; they will use
the same launcher, which handles one connection at a time.

**Where are my settings?**
`%APPDATA%\ss14-autojoin\config.toml`. Delete it to return to the defaults.
