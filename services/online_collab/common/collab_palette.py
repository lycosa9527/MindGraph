"""
Shared collab palette: user colors and emoji pens for workshop avatars.

This module is the single source of truth on the backend. The frontend mirror
is ``frontend/src/shared/collabPalette.ts`` — the two lists must stay in sync
so that a user sees the same color/emoji in the rail and on every peer's
screen. The test ``tests/test_collab_palette_sync.py`` verifies parity at CI
time.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

USER_COLORS: list[str] = [
    "#FF6B6B",
    "#4ECDC4",
    "#45B7D1",
    "#FFA07A",
    "#98D8C8",
    "#F7DC6F",
    "#BB8FCE",
    "#85C1E2",
    "#E11D48",
    "#F59E0B",
    "#65A30D",
    "#059669",
    "#0284C7",
    "#4F46E5",
    "#C026D3",
    "#DB2777",
    "#EA580C",
    "#0D9488",
    "#7C3AED",
    "#2563EB",
]

USER_EMOJIS: list[str] = [
    "✏️",
    "🖊️",
    "✒️",
    "🖋️",
    "📝",
    "✍️",
    "🖍️",
    "🖌️",
    "📎",
    "📐",
    "📏",
    "📌",
    "📍",
    "🔖",
    "✂️",
    "⭐",
    "🍀",
    "🎵",
    "🎯",
    "🔮",
]


def color_for_user(user_id: int) -> str:
    """Deterministic color assignment from user_id (matches the frontend)."""
    idx = abs(int(user_id)) % len(USER_COLORS)
    return USER_COLORS[idx]


def emoji_for_user(user_id: int) -> str:
    """Deterministic emoji assignment from user_id (matches the frontend)."""
    idx = abs(int(user_id)) % len(USER_EMOJIS)
    return USER_EMOJIS[idx]


def palette_for_user(user_id: int) -> tuple[str, str]:
    """Color and emoji for one participant (join roster, lock ring, selection)."""
    return color_for_user(user_id), emoji_for_user(user_id)
