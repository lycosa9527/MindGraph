"""Minimal PNG used as the seeded 双气泡图 cover."""

from __future__ import annotations

import struct
import zlib


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def build_double_bubble_cover_png(width: int = 240, height: int = 144) -> bytes:
    """Return a small PNG with two overlapping circles on a teal field."""
    rows: list[bytes] = []
    cx_a = width * 0.38
    cx_b = width * 0.62
    cy = height * 0.52
    radius = min(width, height) * 0.32
    for y in range(height):
        pixels = bytearray()
        for x in range(width):
            da = (x - cx_a) ** 2 + (y - cy) ** 2
            db = (x - cx_b) ** 2 + (y - cy) ** 2
            in_a = da <= radius**2
            in_b = db <= radius**2
            if in_a and in_b:
                pixels.extend((255, 255, 255, 230))
            elif in_a or in_b:
                pixels.extend((255, 255, 255, 140))
            else:
                pixels.extend((13, 148, 136, 255))
        rows.append(b"\x00" + bytes(pixels))
    raw = b"".join(rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b"")
