"""
Shared ownership and mutability guards for Maite inquiry sessions.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from models.domain.maite_learning import MaiteInquirySession
from repositories.maite.sessions_repo import MaiteSessionsRepository
from services.maite.domain.errors import MaiteConflictError, MaiteNotFoundError


async def require_owned_session(
    sessions: MaiteSessionsRepository,
    session_id: int,
    user_id: int,
) -> MaiteInquirySession:
    """Return an owned session or raise not-found."""
    row = await sessions.get_owned(session_id, user_id)
    if row is None:
        raise MaiteNotFoundError("Session not found")
    return row


async def require_mutable_session(
    sessions: MaiteSessionsRepository,
    session_id: int,
    user_id: int,
) -> MaiteInquirySession:
    """Return an owned session that is not completed (HTTP 409 when locked)."""
    row = await require_owned_session(sessions, session_id, user_id)
    if row.status == "completed":
        raise MaiteConflictError("Completed sessions are read-only")
    return row
