"""Multiscript text width estimates without font metrics.

Keep `_EM_RANGE_TABLE` aligned with `frontend/src/stores/specLoader/textMeasurementFallback.ts`
(`emWidthForCodePoint` ordering and ranges).
"""

from __future__ import annotations

# (start, end, em_width); first match wins (same order as frontend emWidthForCodePoint).
_EM_RANGE_TABLE: tuple[tuple[int, int, float], ...] = (
    (0x300, 0x36F, 0.0),
    (0x1AB0, 0x1AFF, 0.0),
    (0x1DC0, 0x1DFF, 0.0),
    (0x20D0, 0x20FF, 0.0),
    (0xFE00, 0xFE0F, 0.0),
    (0x4E00, 0x9FFF, 1.0),
    (0x3400, 0x4DBF, 1.0),
    (0xF900, 0xFAFF, 1.0),
    (0x20000, 0x2CEAF, 1.0),
    (0x3040, 0x309F, 0.95),
    (0x30A0, 0x30FF, 0.95),
    (0x31F0, 0x31FF, 0.95),
    (0xAC00, 0xD7AF, 0.95),
    (0x1100, 0x11FF, 0.95),
    (0x3130, 0x318F, 0.95),
    (0x0600, 0x06FF, 0.5),
    (0x0750, 0x077F, 0.5),
    (0x08A0, 0x08FF, 0.5),
    (0xFB50, 0xFDFF, 0.5),
    (0xFE70, 0xFEFF, 0.5),
    (0x0590, 0x05FF, 0.52),
    (0x0E00, 0x0E7F, 0.55),
    (0x0900, 0x097F, 0.58),
    (0x0980, 0x09FF, 0.58),
    (0x0A00, 0x0A7F, 0.58),
    (0x0A80, 0x0AFF, 0.58),
    (0x0B00, 0x0B7F, 0.58),
    (0x0B80, 0x0BFF, 0.58),
    (0x0C00, 0x0C7F, 0.58),
    (0x0C80, 0x0CFF, 0.58),
    (0x0D00, 0x0D7F, 0.58),
    (0x0D80, 0x0DFF, 0.58),
    (0x0E80, 0x0EFF, 0.55),
    (0x0F00, 0x0FFF, 0.55),
    (0x1000, 0x109F, 0.55),
    (0x1780, 0x17FF, 0.55),
    (0x10A0, 0x10FF, 0.52),
    (0x2D80, 0x2DDF, 0.55),
    (0xA000, 0xA48F, 0.95),
    (0x4DC0, 0x4DFF, 1.0),
    (0xFF01, 0xFF5E, 0.55),
    (0xFF10, 0xFF19, 0.55),
    (0x30, 0x39, 0.55),
    (0x41, 0x5A, 0.58),
    (0x61, 0x7A, 0.55),
    (0xC0, 0x24F, 0.55),
    (0x370, 0x3FF, 0.55),
    (0x400, 0x4FF, 0.58),
    (0x500, 0x52F, 0.58),
    (0x1E00, 0x1EFF, 0.55),
    (0x2C60, 0x2C7F, 0.55),
)


def _em_width_for_code_point(code_point: int) -> float:
    if code_point <= 0x20:
        return 0.28 if code_point == 0x20 else 0.0
    for start, end, em in _EM_RANGE_TABLE:
        if start <= code_point <= end:
            return em
    return 0.62


def estimate_text_width_px(
    text: str,
    font_size: float,
    *,
    is_topic: bool = False,
) -> float:
    """Estimated text width in px (no DOM). Bold/topic uses a slight advance bump."""
    sample = (text or "").strip() or " "
    em_total = 0.0
    for ch in sample:
        em_total += _em_width_for_code_point(ord(ch))
    bold = 1.04 if is_topic else 1.0
    return max(font_size * 0.35, em_total * font_size * bold)
