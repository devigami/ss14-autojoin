"""Get the player's attention when the join lands. Standard library only.

The join sound is ``data/fanfare.wav`` (synthesized in this repository, public domain). Windows plays it
through ``winsound``; macOS through ``afplay``; Linux through ``paplay`` or ``aplay`` when present; otherwise the
terminal bell. Nothing here may raise: a notification must never break the loop.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path


def fanfare_path() -> Path | None:
    """The bundled WAV, or None when it is missing (also works inside a PyInstaller one-file build)."""
    try:
        path = Path(str(resources.files("ss14_autojoin").joinpath("data", "fanfare.wav")))
        return path if path.is_file() else None
    except Exception:  # noqa: BLE001
        return None


def play_success() -> None:
    """Play the fanfare (asynchronously where the platform allows); fall back to the alert sound."""
    path = fanfare_path()
    try:
        if path is None:
            beep(3)
            return
        if sys.platform == "win32":
            import winsound  # noqa: PLC0415

            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            return
        player = next((p for p in ("afplay", "paplay", "aplay") if shutil.which(p)), None)
        if player:
            subprocess.Popen([player, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            beep(3)
    except Exception:  # noqa: BLE001
        beep(1)


def beep(times: int = 1) -> None:
    """The system alert sound; silent when unavailable."""
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
    except Exception:  # noqa: BLE001
        pass


def _pause() -> None:
    import time  # noqa: PLC0415

    time.sleep(0.35)
