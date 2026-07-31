"""
Maite inquiry sessions repository.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select

from models.domain.maite_learning import MaiteInquirySession
from repositories.base import BaseRepository


class MaiteSessionsRepository(BaseRepository[MaiteInquirySession]):
    """Async CRUD helpers for ``maite_inquiry_sessions``."""

    model = MaiteInquirySession

    async def list_for_user(
        self,
        user_id: int,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[MaiteInquirySession]:
        """List inquiry sessions for a user, most recently updated first."""
        stmt = (
            select(MaiteInquirySession)
            .where(MaiteInquirySession.user_id == user_id)
            .order_by(MaiteInquirySession.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_owned(self, session_id: int, user_id: int) -> Optional[MaiteInquirySession]:
        """Fetch a session only when it belongs to ``user_id``."""
        stmt = select(MaiteInquirySession).where(
            MaiteInquirySession.id == session_id,
            MaiteInquirySession.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
