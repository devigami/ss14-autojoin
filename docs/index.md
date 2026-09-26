# SS14 Auto-Join

**Get into a full Space Station 14 server without hammering the Connect button.**

SS14 Auto-Join is a small Windows program that watches one server and, the moment a player slot opens, tells
the official Space Station 14 launcher to connect, exactly as if you had pressed Connect yourself. It then
checks whether you actually got in. If someone else took the slot first, it closes the rejected game client
and goes back to watching. When the join succeeds it plays a short fanfare and leaves you in the game.

!!! warning "Tested on Windows only"
    Everything has been verified on Windows 11 with the Steam edition of the launcher. Linux and macOS builds
    are produced but untested. If something does not work for you, please
    [open an issue](https://github.com/devigami/ss14-autojoin/issues/new/choose) with the log from the window.

## What it does

* Polls the server's public status page every few seconds and waits for `players < max`.
* Asks the real launcher to connect. The launcher handles your login, the content download and the game
  start; Auto-Join never sees your account or token.
* Confirms the join from the game client's network state and the client log, then stops (or keeps watching
  and rejoins, if you ask it to).
* Closes a rejected client and tries again on the next free slot. Bans, whitelists and panic bunkers stop it:
  it only retries when the server said "full".

## What it does not do

* It does not bypass anything. It joins the same way you do, one attempt per free slot, and respects the
  server's admission rules.
* It does not spam the server. Status polling is three seconds apart by default and never faster than once a
  second, and connection attempts happen only when the status page shows a free slot.
* It does not touch your account. Login stays inside the official launcher.

## Where next

* [Getting started](getting-started.md): download, first run, the settings window.
* [How it works](how-it-works.md): the loop, and how success and failure are detected.
* [Settings](settings.md) and the [command line](command-line.md).
* [Troubleshooting](troubleshooting.md) and the [FAQ](faq.md).
* [Privacy](privacy.md): nothing is collected; here is what the program touches.
