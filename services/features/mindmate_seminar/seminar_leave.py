"""A joiner leaves a live MindMate seminar without ending it for everyone else.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from models.domain.mindmate_seminar import MindmateSeminarMember, MindmateSeminarSession
from services.features.mindmate_seminar.manager_access import get_mindmate_seminar_manager
from utils.db.session_open import system_rls_session


async def session_ids_viewer_left(user_id: int) -> set[str]:
    """Live-list session ids this person has already quit."""
    async with system_rls_session() as db:
        rows = (
            (
                await db.execute(
                    select(MindmateSeminarMember.session_id).where(
                        MindmateSeminarMember.user_id == user_id,
                        MindmateSeminarMember.left_at.is_not(None),
                    ),
                )
            )
            .scalars()
            .all()
        )
    return {str(row) for row in rows}


async def leave_live_seminar(user_id: int, session_id: str) -> str:
    """Record that user_id quit a live seminar.

    Returns ``ok``, ``not_found``, or ``still_owner``. The owner must end the
    room. A person with no membership row still gets a left marker so an
    org-visible room drops off their sidebar.
    """
    now = datetime.now(tz=UTC)
    async with system_rls_session() as db:
        session = await db.get(MindmateSeminarSession, session_id)
        if session is None or session.ended_at is not None:
            return "not_found"
        if session.owner_user_id == user_id:
            return "still_owner"
        member = await db.get(MindmateSeminarMember, (session_id, user_id))
        if member is None:
            db.add(
                MindmateSeminarMember(
                    session_id=session_id,
                    user_id=user_id,
                    joined_at=now,
                    seminar_role="participant",
                    accepted=False,
                    left_at=now,
                ),
            )
        else:
            member.left_at = now
        code = session.code
        await db.commit()
    await get_mindmate_seminar_manager().remove_participant(code, user_id)
    return "ok"
