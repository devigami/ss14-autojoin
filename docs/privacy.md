# Privacy policy

*Last updated 2026-09-26.*

SS14 Auto-Join collects no personal data. It has no accounts, no telemetry, no analytics, no crash reporting
and no update checks. Nothing you do with it is sent to the project or to anyone else. This page explains
what the program does touch, so the statement above can be checked rather than taken on trust.

## What the program does on your computer

| Activity | Detail |
|---|---|
| Network requests | `GET` requests to the public `/status` page of the one game server you configure, at the interval you set (three seconds by default). The request carries a `User-Agent` header naming the tool and its version, and your IP address, as any web request does. That server's operators may log it; the project does not receive it. No other host is contacted. |
| Starting programs | The official Space Station 14 launcher, with the server address as its argument. The launcher then does what it always does when you press Connect: it logs you in and starts the game. Those steps are governed by the [Space Station 14 privacy policy](https://spacestation14.com/about/privacy/), not by this one. The tool never sees your account, password or login token. |
| Stopping programs | Only a game client the tool started, and only after the server rejected it. |
| Reading files | The launcher's own log files (to learn the game client's process ID and the reason for a rejection), Steam's library list and the Windows registry entry for Steam's location (to find the launcher). Those files may contain your account name; the tool reads them in memory and stores nothing from them. |
| Writing files | One settings file, `%APPDATA%\ss14-autojoin\config.toml`, containing the options you chose (launcher folder, server address, timings, switches). It never contains credentials. Delete it to remove every trace of the program's configuration. |

The program keeps no history of servers watched or joins made beyond the log shown in its window, which is
discarded when the window closes.

## Websites and services around the project

* **Downloads, source code, issues and releases** are hosted on GitHub and subject to the
  [GitHub Privacy Statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement).
  Anything you post in an issue is public; the issue templates ask for logs, so remove your account name or
  anything else you would rather not publish before posting.
* **This documentation site** is served by GitHub Pages, which may log requests as described in the same
  statement. The site itself contains no analytics or third-party scripts beyond the fonts and assets of its
  theme.
* **Installing through winget** involves the Windows Package Manager, which is Microsoft's software and
  subject to Microsoft's privacy statement.

## Children

The program is a utility for players of Space Station 14 and is not directed at children. It collects no data
from anyone, of any age.

## Changes

If a future version ever collects or transmits anything beyond what is listed here, this page will say so
before that version is released, the change will be called out in the release notes, and the feature will be
opt-in.

## Contact

Questions about this policy: open an issue at <https://github.com/devigami/ss14-autojoin/issues>. For a
security concern, use the private route described in the project's
[security policy](https://github.com/devigami/ss14-autojoin/blob/master/SECURITY.md).
