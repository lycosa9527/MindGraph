"""Age helper for the MindMate seminar Redis safety window.

A seminar stays live until its leader ends it. This module does not close rooms.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from services.features.mindmate_seminar.config import MINDMATE_COLLAB_MAX_LIVE_SECONDS


def seminar_past_max_live_age(started_at: datetime, now: datetime) -> bool:
    """True when a live window that began at started_at is at least 30 days old.

    Callers use this for the Redis key window. It does not end the seminar.
    """
    started = started_at if started_at.tzinfo is not None else started_at.replace(tzinfo=UTC)
    current = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    age = current.astimezone(UTC) - started.astimezone(UTC)
    return age >= timedelta(seconds=MINDMATE_COLLAB_MAX_LIVE_SECONDS)


async def expire_overdue_live_seminars() -> int:
    """Do not close live seminars by age. The leader ends the room."""
    return 0
