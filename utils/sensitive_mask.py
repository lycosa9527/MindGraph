"""Mask sensitive strings for public or list API responses (not encryption)."""

from __future__ import annotations

from typing import Optional


def mask_invitation_code(raw: Optional[str]) -> Optional[str]:
    """
    Return a non-reversible preview of an invitation code for list endpoints.

    Full codes must be fetched via an explicit admin read endpoint when needed.
    """
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None
    if len(s) <= 4:
        return "****"
    head, tail = s[:2], s[-2:]
    mid_len = min(8, max(4, len(s) - 4))
    return f"{head}{'*' * mid_len}{tail}"
