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
]


def color_for_user(user_id: int) -> str:
    """Deterministic color assignment from user_id (matches the frontend)."""
    idx = abs(int(user_id)) % len(USER_COLORS)
    return USER_COLORS[idx]


def emoji_for_user(user_id: int) -> str:
    """Deterministic emoji assignment from user_id (matches the frontend)."""
    idx = abs(int(user_id)) % len(USER_EMOJIS)
    return USER_EMOJIS[idx]
