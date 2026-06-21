"""
Shared export date-range helpers (activity overlap, inclusive bounds).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional


def activity_overlaps_range(
    first_activity: int,
    last_activity: int,
    start: Optional[int],
    end: Optional[int],
) -> bool:
    """
    Return True when activity interval intersects the export window (inclusive).

    ``first_activity`` / ``last_activity`` are UTC epoch seconds bounding the
    conversation or thread. When a range is set, any overlap with
    ``[start, end]`` qualifies; once included, callers fetch the full thread.
    """
    if start is None and end is None:
        return True
    first = first_activity if first_activity > 0 else last_activity
    last = last_activity if last_activity > 0 else first_activity
    if first <= 0 and last <= 0:
        return start is None and end is None
    if start is not None and last < start:
        return False
    if end is not None and first > end:
        return False
    return True


def conversation_overlaps_export_range(
    created_at: int,
    updated_at: int,
    start: Optional[int],
    end: Optional[int],
) -> bool:
    """True when a Dify conversation row overlaps the export window."""
    first = created_at if created_at > 0 else updated_at
    last = updated_at if updated_at > 0 else created_at
    return activity_overlaps_range(first, last, start, end)
