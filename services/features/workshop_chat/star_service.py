"""
Star Service
==============

Starred/bookmarked message operations.

Follows Zulip's ``starred_messages`` pattern where users can bookmark
messages for later reference.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Any, Dict, List, Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from models.domain.workshop_chat import ChatMessage, StarredMessage

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 50


class StarService:
    """Starred message operations."""

    @staticmethod
    async def toggle_star(
        db: AsyncSession,
        message_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """Star a message if not starred, unstar if already starred.

        Returns ``{"action": "starred"|"unstarred", ...}``.
        """
        result = await db.execute(
            select(StarredMessage).where(
                StarredMessage.message_id == message_id,
                StarredMessage.user_id == user_id,
            )
        )
        existing = result.scalars().first()
        if existing:
            await db.delete(existing)
            await db.commit()
            return {"action": "unstarred", "message_id": message_id}

        star = StarredMessage(message_id=message_id, user_id=user_id)
        db.add(star)
        await db.commit()
        return {"action": "starred", "message_id": message_id}

    @staticmethod
    async def get_starred_messages(
        db: AsyncSession,
        user_id: int,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get a user's starred messages, most recently starred first."""
        result = await db.execute(
            select(StarredMessage)
            .where(StarredMessage.user_id == user_id)
            .options(
                joinedload(StarredMessage.message).joinedload(ChatMessage.sender),
            )
            .order_by(StarredMessage.created_at.desc())
            .offset(offset)
            .limit(min(limit, 200))
        )
        stars = result.scalars().unique().all()
        results: List[Dict[str, Any]] = []
        for star in stars:
            msg = star.message
            if not msg or msg.is_deleted:
                continue
            sender = msg.sender
            results.append(
                {
                    "star_id": star.id,
                    "starred_at": star.created_at.isoformat(),
                    "message": {
                        "id": msg.id,
                        "channel_id": msg.channel_id,
                        "topic_id": msg.topic_id,
                        "sender_id": msg.sender_id,
                        "sender_name": sender.name if sender else f"User {msg.sender_id}",
                        "sender_avatar": sender.avatar if sender else None,
                        "content": msg.content,
                        "message_type": msg.message_type,
                        "created_at": msg.created_at.isoformat(),
                    },
                }
            )
        return results

    @staticmethod
    async def is_starred_batch(
        db: AsyncSession,
        message_ids: List[int],
        user_id: int,
    ) -> Set[int]:
        """Return the subset of *message_ids* that the user has starred."""
        if not message_ids:
            return set()
        result = await db.execute(
            select(StarredMessage.message_id).where(
                StarredMessage.user_id == user_id,
                StarredMessage.message_id.in_(message_ids),
            )
        )
        return set(result.scalars().all())


star_service = StarService()
