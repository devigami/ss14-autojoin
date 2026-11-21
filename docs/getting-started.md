# Getting started

## 1. Install

### With winget (recommended)

The Windows Package Manager is part of Windows 10 and 11. In a terminal:

```powershell
winget install Devigami.SS14AutoJoin
```

This installs the window as a command rather than a Start menu entry: open a **new** terminal and run
`SS14AutoJoin`. winget checks the download against the hash in the reviewed package manifest, and Windows
does not show its "Windows protected your PC" prompt for a program installed this way.

Later, `winget upgrade Devigami.SS14AutoJoin` updates it and `winget uninstall Devigami.SS14AutoJoin` removes
it. A new version appears in winget a few days after it is released here, once the package repository's
reviewers have approved it.

### By download

Grab `SS14AutoJoin-<version>-windows-x64.exe` from the
[releases page](https://github.com/devigami/ss14-autojoin/releases/latest). It is a single file; put it
anywhere. A console version, `ss14-autojoin-<version>-windows-x64.exe`, is attached to the same release for
people who prefer a terminal (see [Command line](command-line.md)).

!!! note "Windows protected your PC"
    The executable is not code-signed, so Windows shows this prompt the first time you run a copy downloaded
    with a browser. Choose **More info** and **Run anyway**, after comparing the file with `SHA256SUMS.txt`
    on the release if you like. Installing with winget or building from source (below) avoids the prompt.

### Which version do I have?

The title bar shows it (from 1.0.1), as does `winget list Devigami.SS14AutoJoin`. From a terminal,
`SS14AutoJoin --version` prints it without opening the window; see [Command line](command-line.md#which-version).

You need the official Space Station 14 launcher installed (Steam or standalone) and to have logged in with it
at least once.

## 2. First run

Start SS14 Auto-Join: `SS14AutoJoin` after a winget install, or the downloaded file. The window has three
parts: the settings panel, the Start/Stop and Save buttons,
and a log.

1. **Game / launcher folder** is filled in automatically when the launcher can be found: a running
   launcher, the launcher's own log, your Steam libraries and the usual places for the standalone zip are all
   checked. If it is empty, press **Detect**, or **Browse…** to the folder that contains `bin_x64`
   (for Steam that is `…\steamapps\common\Space Station 14 Playtest` or `…\Space Station 14`).
2. **Server address** is the server's `ss14://` or `ss14s://` address. The easiest way to find it: in the
   launcher, add the server to your favourites and look at the launcher log, or take it from the server's
   own website or Discord. The default is Wizard's Den Lizard, `ss14s://lizard.spacestation14.io/server`.
   For most community servers the address is simply `ss14://host` or `ss14://host:port`.
3. Leave the numbers at their defaults for a first run. See [Settings](settings.md) for what they do.
4. Press **Start watching**. The log shows the player count each time it changes, then the attempt, the
   game client starting, and finally `joined`. The fanfare plays and the tool stops, leaving the game open.

Press **Save settings** to keep your choices for next time. They are stored in
`%APPDATA%\ss14-autojoin\config.toml`.

## 3. While it waits

Leave the window open. It is fine to do other things; the game client only appears when a slot is free. When
the join lands the window comes to the front and plays the fanfare (turn that off with the check box).

If the server rejects the attempt because the slot was taken, the log shows the reason once the client has
been closed, and watching resumes after a two-second pause.

## Running from source

With [uv](https://docs.astral.sh/uv/) installed:

```powershell
git clone https://github.com/devigami/ss14-autojoin
cd ss14-autojoin
uv sync --all-groups
uv run ss14-autojoin gui
```

`uv run python build.py` produces `dist\SS14AutoJoin.exe`; add `--cli` for the console executable.
