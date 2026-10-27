"""
Remember who joined a MindMate seminar.

The Redis participant set is live only. This row stays after the socket
closes so a finished seminar can appear in that person's history.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert

from models.domain.mindmate_collab import MindmateCollabMember
from services.utils.error_types import DATABASE_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)


async def record_collab_member(session_id: str, user_id: int) -> None:
    """Insert a join row. A repeat join keeps the first joined_at and clears a prior leave."""
    if not session_id or user_id <= 0:
        return
    stmt = (
        pg_insert(MindmateCollabMember)
        .values(
            session_id=session_id,
            user_id=user_id,
            joined_at=datetime.now(tz=UTC),
            accepted=True,
        )
        .on_conflict_do_update(
            index_elements=["session_id", "user_id"],
            set_={"left_at": None, "accepted": True},
        )
    )
    try:
        async with system_rls_session() as db:
            await db.execute(stmt)
            await db.commit()
    except DATABASE_ERRORS as exc:
        logger.warning(
            "[MindmateCollab] Could not record member session=%s user=%s: %s",
            session_id,
            user_id,
            exc,
        )
