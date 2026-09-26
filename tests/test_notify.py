from __future__ import annotations

import wave

from ss14_autojoin import notify


def test_fanfare_is_bundled_and_short() -> None:
    path = notify.fanfare_path()
    assert path is not None and path.name == "fanfare.wav"
    with wave.open(str(path), "rb") as wav:
        assert wav.getnchannels() == 1 and wav.getsampwidth() == 2 and wav.getframerate() == 44100
        seconds = wav.getnframes() / wav.getframerate()
    assert 1.0 < seconds < 2.5
    assert path.stat().st_size < 200_000


def test_play_and_beep_never_raise(monkeypatch) -> None:
    monkeypatch.setattr(notify, "fanfare_path", lambda: None)
    monkeypatch.setattr(notify, "_pause", lambda: None)
    notify.play_success()
    notify.beep(2)
    monkeypatch.setattr(notify.shutil, "which", lambda name: None)
    monkeypatch.undo()
    monkeypatch.setattr(notify, "_pause", lambda: None)
    monkeypatch.setattr(notify.shutil, "which", lambda name: None)
    if notify.sys.platform != "win32":
        notify.play_success()  # falls back to the bell without a player
