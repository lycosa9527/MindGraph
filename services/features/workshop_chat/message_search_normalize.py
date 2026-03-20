"""Normalize query and limit for ILIKE message search (Zulip-style narrow)."""

from typing import Optional, Tuple


def ilike_pattern_from_text(text: str, limit: int) -> Tuple[Optional[str], int]:
    """Return ``(ILIKE pattern, limit)``; pattern is None when there is nothing to search."""
    raw = (text or "").strip()
    if not raw or len(raw) > 200:
        return None, 0
    lim = min(max(limit, 1), 100)
    return f"%{raw}%", lim
