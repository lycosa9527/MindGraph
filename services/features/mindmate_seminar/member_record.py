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

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models.domain.mindmate_seminar import MindmateSeminarMember, MindmateSeminarSession
from services.features.mindmate_seminar.seminar_roles import SEMINAR_ROLE_LEADER, SEMINAR_ROLE_UNASSIGNED
from services.utils.error_types import DATABASE_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)


async def record_collab_member(session_id: str, user_id: int) -> None:
    """Insert a join row. A repeat join keeps the first joined_at and clears a prior leave."""
    if not session_id or user_id <= 0:
        return
    try:
        async with system_rls_session() as db:
            owner_id = (
                await db.execute(
                    select(MindmateSeminarSession.owner_user_id).where(MindmateSeminarSession.id == session_id)
                )
            ).scalar_one_or_none()
            is_owner = owner_id is not None and int(owner_id) == int(user_id)
            role = SEMINAR_ROLE_LEADER if is_owner else SEMINAR_ROLE_UNASSIGNED
            kept = {"left_at": None, "accepted": True}
            if is_owner:
                kept["seminar_role"] = SEMINAR_ROLE_LEADER
            stmt = (
                pg_insert(MindmateSeminarMember)
                .values(
                    session_id=session_id,
                    user_id=user_id,
                    joined_at=datetime.now(tz=UTC),
                    accepted=True,
                    invited=False,
                    seminar_role=role,
                )
                .on_conflict_do_update(
                    index_elements=["session_id", "user_id"],
                    set_=kept,
                )
            )
            await db.execute(stmt)
            await db.commit()
    except DATABASE_ERRORS as exc:
        logger.warning(
            "[MindmateSeminar] Could not record member session=%s user=%s: %s",
            session_id,
            user_id,
            exc,
        )
