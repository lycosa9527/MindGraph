"""Close a live MindMate seminar that the owner left open for 24 hours.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from models.domain.mindmate_collab import MindmateCollabSession
from services.features.mindmate_collab.config import MINDMATE_COLLAB_MAX_LIVE_SECONDS
from services.features.mindmate_collab.manager_access import get_mindmate_collab_manager
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_EXPIRE_BATCH = 20
_STOP_ERRORS = BACKGROUND_INFRA_ERRORS + (SQLAlchemyError, RedisError)


def seminar_past_max_live_age(started_at: datetime, now: datetime) -> bool:
    """True when a live window that began at started_at is at least 24 hours old."""
    started = started_at if started_at.tzinfo is not None else started_at.replace(tzinfo=UTC)
    current = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    age = current.astimezone(UTC) - started.astimezone(UTC)
    return age >= timedelta(seconds=MINDMATE_COLLAB_MAX_LIVE_SECONDS)


async def expire_overdue_live_seminars() -> int:
    """Stop live seminars whose started_at is older than the 24-hour cap."""
    cutoff = datetime.now(tz=UTC) - timedelta(seconds=MINDMATE_COLLAB_MAX_LIVE_SECONDS)
    try:
        async with system_rls_session() as db:
            result = await db.execute(
                select(MindmateCollabSession.id)
                .where(
                    MindmateCollabSession.ended_at.is_(None),
                    MindmateCollabSession.started_at <= cutoff,
                )
                .order_by(MindmateCollabSession.started_at.asc())
                .limit(_EXPIRE_BATCH),
            )
            rows = result.scalars().all()
    except _STOP_ERRORS as exc:
        logger.warning("[MindmateCollabTTL] sweep failed: %s", exc)
        return 0
    manager = get_mindmate_collab_manager()
    stopped = 0
    for session_id in rows:
        try:
            ok = await manager.stop_session(str(session_id), 0, reason="expired")
        except _STOP_ERRORS as exc:
            logger.warning(
                "[MindmateCollabTTL] expire failed session=%s: %s",
                session_id,
                exc,
            )
            continue
        if ok:
            stopped += 1
    if stopped:
        logger.info("[MindmateCollabTTL] auto-closed %s seminar(s) past 24h", stopped)
    return stopped
