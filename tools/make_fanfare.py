"""Generate ``src/ss14_autojoin/data/fanfare.wav``: a short brass "ta-da" (C5 E5 G5 C6), synthesized here.

Pure standard library. The result is released to the public domain (CC0): nothing sampled, nothing
downloaded. Run: ``uv run python tools/make_fanfare.py``.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

RATE = 44100
OUT = Path(__file__).resolve().parents[1] / "src" / "ss14_autojoin" / "data" / "fanfare.wav"

# (frequency Hz, duration s, gap after s)
NOTES = [(523.25, 0.16, 0.03), (659.25, 0.16, 0.03), (783.99, 0.16, 0.03), (1046.50, 0.80, 0.0)]
# Brass-like spectrum: strong low harmonics, a bright bump around the 4th and 5th, rolling off above.
HARMONICS = [1.0, 0.85, 0.6, 0.55, 0.45, 0.25, 0.15, 0.1, 0.06]


def envelope(t: float, duration: float) -> float:
    attack, release = 0.025, 0.12
    if t < attack:
        return t / attack
    if t > duration - release:
        return max(0.0, (duration - t) / release)
    return 1.0 - 0.15 * (t - attack) / max(duration - attack - release, 1e-6)


def render() -> list[int]:
    samples: list[int] = []
    for freq, duration, gap in NOTES:
        n = int(RATE * duration)
        for i in range(n):
            t = i / RATE
            vibrato = 1.0 + 0.004 * math.sin(2 * math.pi * 5.5 * t)
            brightness = 1.0 + 0.6 * min(t / 0.05, 1.0)  # the "blat" of a brass attack opens up over 50 ms
            value = 0.0
            for k, amp in enumerate(HARMONICS, start=1):
                weight = amp * (brightness if k >= 3 else 1.0)
                value += weight * math.sin(2 * math.pi * freq * vibrato * k * t)
            value *= envelope(t, duration) * 0.28
            samples.append(int(max(-1.0, min(1.0, value)) * 32767))
        samples.extend([0] * int(RATE * gap))
    samples.extend([0] * int(RATE * 0.1))
    return samples


def main() -> None:
    samples = render()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    print(f"wrote {OUT} ({len(samples) / RATE:.2f} s, {OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
