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


def test_icon_files_are_bundled() -> None:
    import struct
    from importlib import resources
    from pathlib import Path

    data = resources.files("ss14_autojoin").joinpath("data")
    png = Path(str(data.joinpath("icon.png"))).read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", png[16:24]) == (256, 256)
    ico = Path(str(data.joinpath("icon.ico"))).read_bytes()
    reserved, kind, count = struct.unpack("<HHH", ico[:6])
    assert (reserved, kind, count) == (0, 1, 6)
    sizes = {struct.unpack("<B", ico[6 + 16 * i : 7 + 16 * i])[0] or 256 for i in range(count)}
    assert sizes == {256, 128, 64, 48, 32, 16}
