"""Generate the app icon: a ring space station, drawn with the standard library only.

Writes ``src/ss14_autojoin/data/icon.png`` (256 px) and ``icon.ico`` (16 to 256 px, PNG-compressed entries).
Public domain (CC0). Run: ``uv run python tools/make_icon.py``.
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "src" / "ss14_autojoin" / "data"
SUPER = 1024  # render size; downsampled with a box filter for anti-aliasing
SIZES = (256, 128, 64, 48, 32, 16)

Color = tuple[int, int, int, int]
SPACE = (16, 22, 38, 255)
SPACE_EDGE = (34, 44, 70, 255)
HULL = (196, 204, 216, 255)
HULL_DARK = (128, 138, 156, 255)
HULL_LIGHT = (236, 240, 246, 255)
PANEL = (44, 96, 190, 255)
PANEL_LINE = (26, 60, 130, 255)
GLOW = (255, 170, 60, 255)
STAR = (230, 236, 255, 255)


class Canvas:
    def __init__(self, size: int) -> None:
        self.size = size
        self.px: list[Color] = [(0, 0, 0, 0)] * (size * size)

    def blend(self, x: int, y: int, c: Color) -> None:
        if not (0 <= x < self.size and 0 <= y < self.size):
            return
        a = c[3] / 255
        if a >= 1.0:
            self.px[y * self.size + x] = c
            return
        r, g, b, oa = self.px[y * self.size + x]
        na = a + (oa / 255) * (1 - a)
        if na == 0:
            return
        blend = lambda cn, co: int((cn * a + co * (oa / 255) * (1 - a)) / na)  # noqa: E731
        self.px[y * self.size + x] = (blend(c[0], r), blend(c[1], g), blend(c[2], b), int(na * 255))

    def disc(self, cx: float, cy: float, radius: float, c: Color) -> None:
        r2 = radius * radius
        for y in range(max(0, int(cy - radius)), min(self.size, int(cy + radius) + 2)):
            for x in range(max(0, int(cx - radius)), min(self.size, int(cx + radius) + 2)):
                if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r2:
                    self.blend(x, y, c)

    def ring(self, cx: float, cy: float, outer: float, inner: float, c: Color) -> None:
        o2, i2 = outer * outer, inner * inner
        for y in range(max(0, int(cy - outer)), min(self.size, int(cy + outer) + 2)):
            for x in range(max(0, int(cx - outer)), min(self.size, int(cx + outer) + 2)):
                d2 = (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2
                if i2 <= d2 <= o2:
                    self.blend(x, y, c)

    def bar(self, x0: float, y0: float, x1: float, y1: float, width: float, c: Color) -> None:
        """A thick line segment with square ends."""
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy) or 1.0
        ux, uy = dx / length, dy / length
        half = width / 2
        xs = [x0 - uy * half, x0 + uy * half, x1 + uy * half, x1 - uy * half]
        ys = [y0 + ux * half, y0 - ux * half, y1 - ux * half, y1 + ux * half]
        for y in range(max(0, int(min(ys))), min(self.size, int(max(ys)) + 2)):
            for x in range(max(0, int(min(xs))), min(self.size, int(max(xs)) + 2)):
                px, py = x + 0.5 - x0, y + 0.5 - y0
                along = px * ux + py * uy
                across = abs(-px * uy + py * ux)
                if 0 <= along <= length and across <= half:
                    self.blend(x, y, c)

    def downsample(self, size: int) -> Canvas:
        out = Canvas(size)
        factor = self.size // size
        area = factor * factor
        for y in range(size):
            for x in range(size):
                r = g = b = a = 0
                for sy in range(factor):
                    row = (y * factor + sy) * self.size + x * factor
                    for sx in range(factor):
                        pr, pg, pb, pa = self.px[row + sx]
                        r += pr * pa
                        g += pg * pa
                        b += pb * pa
                        a += pa
                if a:
                    out.px[y * size + x] = (r // a, g // a, b // a, a // area)
        return out

    def png(self) -> bytes:
        raw = bytearray()
        for y in range(self.size):
            raw.append(0)
            for x in range(self.size):
                raw.extend(self.px[y * self.size + x])

        def chunk(kind: bytes, data: bytes) -> bytes:
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

        header = struct.pack(">IIBBBBB", self.size, self.size, 8, 6, 0, 0, 0)
        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b"")
        )


def draw() -> Canvas:
    c = Canvas(SUPER)
    s = SUPER
    cx = cy = s / 2
    # Space: a dark disc with a slightly lighter rim so the icon has an edge on any background.
    c.disc(cx, cy, s * 0.48, SPACE_EDGE)
    c.disc(cx, cy, s * 0.455, SPACE)
    for fx, fy, fr in (
        (0.18, 0.22, 0.010),
        (0.80, 0.17, 0.008),
        (0.24, 0.79, 0.007),
        (0.86, 0.70, 0.010),
        (0.60, 0.12, 0.006),
    ):
        c.disc(s * fx, s * fy, s * fr, STAR)
    # Solar panels: two wings on a thin truss, behind the ring.
    truss_y = cy
    c.bar(s * 0.10, truss_y, s * 0.90, truss_y, s * 0.028, HULL_DARK)
    for x0 in (0.05, 0.75):
        px0, px1 = s * x0, s * (x0 + 0.20)
        for i in range(3):
            y0 = cy - s * 0.09 + i * s * 0.06
            c.bar(px0, y0, px1, y0, s * 0.052, PANEL)
            c.bar(px0, y0 + s * 0.026, px1, y0 + s * 0.026, s * 0.006, PANEL_LINE)
        c.bar((px0 + px1) / 2, cy - s * 0.12, (px0 + px1) / 2, cy + s * 0.12, s * 0.008, PANEL_LINE)
    # The ring, with a lighter top edge for a hint of volume.
    c.ring(cx, cy, s * 0.36, s * 0.27, HULL_DARK)
    c.ring(cx, cy - s * 0.008, s * 0.352, s * 0.278, HULL)
    # Spokes.
    for angle in (90, 210, 330):
        a = math.radians(angle)
        c.bar(cx, cy, cx + math.cos(a) * s * 0.30, cy - math.sin(a) * s * 0.30, s * 0.045, HULL_DARK)
        c.bar(cx, cy, cx + math.cos(a) * s * 0.30, cy - math.sin(a) * s * 0.30, s * 0.028, HULL)
    # Hub with a warm lit window: the orange accent that reads as "occupied".
    c.disc(cx, cy, s * 0.135, HULL_DARK)
    c.disc(cx, cy - s * 0.006, s * 0.12, HULL_LIGHT)
    c.disc(cx, cy, s * 0.07, GLOW)
    c.disc(cx - s * 0.02, cy - s * 0.02, s * 0.022, (255, 232, 170, 255))
    return c


def ico(images: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, payload = b"", b""
    for size, data in images:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset + len(payload))
        payload += data
    return header + entries + payload


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    big = draw()
    pngs = [(size, big.downsample(size).png()) for size in SIZES]
    (OUT_DIR / "icon.png").write_bytes(pngs[0][1])
    (OUT_DIR / "icon.ico").write_bytes(ico(pngs))
    for size, data in pngs:
        print(f"{size:>3} px: {len(data)} bytes")
    print(f"wrote {OUT_DIR / 'icon.png'} and {OUT_DIR / 'icon.ico'}")


if __name__ == "__main__":
    main()
