"""Get the player's attention when the join lands (or the loop stops). Standard library only."""

from __future__ import annotations

import sys


def beep(times: int = 3) -> None:
    """Play the system alert sound; silent when no sound device or API is available."""
    try:
        if sys.platform == "win32":
            import winsound  # noqa: PLC0415

            for _ in range(times):
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
                _pause()
        else:
            for _ in range(times):
                sys.stdout.write("\a")
                sys.stdout.flush()
                _pause()
    except Exception:  # noqa: BLE001 - a notification must never break the loop
        pass


def _pause() -> None:
    import time  # noqa: PLC0415

    time.sleep(0.35)
