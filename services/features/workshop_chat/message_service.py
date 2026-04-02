"""
Message Service
=================

Channel and topic message operations.

Follows Zulip's ``zerver/actions/message_send.py`` /
``zerver/actions/message_edit.py`` split: one module owns all
message write and query logic.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from models.domain.auth import User
from models.domain.workshop_chat import (
    ChannelMember,
    ChatChannel,
    ChatMessage,
    ChatTopic,
)
from services.features.workshop_chat.mention_resolution import (
    resolve_mentioned_user_ids,
)
from services.features.workshop_chat import message_fts
from utils.auth.roles import can_moderate_workshop_channel

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
MAX_CONTENT_LENGTH = 5000


def _format_message(msg: ChatMessage) -> Dict[str, Any]:
    """Format a ChatMessage ORM object into a response dict."""
    sender = msg.sender
    mention_ids = msg.mentioned_user_ids
    return {
        "id": msg.id,
        "channel_id": msg.channel_id,
        "topic_id": msg.topic_id,
        "sender_id": msg.sender_id,
        "sender_name": sender.name if sender else f"User {msg.sender_id}",
        "sender_avatar": sender.avatar if sender else None,
        "content": msg.content,
        "message_type": msg.message_type,
        "parent_id": msg.parent_id,
        "is_deleted": msg.is_deleted,
        "mentioned_user_ids": list(mention_ids) if mention_ids else [],
        "created_at": msg.created_at.isoformat(),
        "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
    }


class MessageService:
    """Channel and topic message operations."""

    @staticmethod
    async def get_channel_messages(
        db: AsyncSession,
        channel_id: int,
        anchor: int = 0,
        num_before: int = DEFAULT_PAGE_SIZE,
        num_after: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get general channel messages (topic_id is NULL), anchor-based."""
        return await MessageService._fetch(
            db,
            channel_id=channel_id,
            topic_id=None,
            general_only=True,
            anchor=anchor,
            num_before=num_before,
            num_after=num_after,
        )

    @staticmethod
    async def get_topic_messages(
        db: AsyncSession,
        topic_id: int,
        channel_id: int,
        anchor: int = 0,
        num_before: int = DEFAULT_PAGE_SIZE,
        num_after: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get messages for a specific topic, anchor-based."""
        return await MessageService._fetch(
            db,
            channel_id=channel_id,
            topic_id=topic_id,
            general_only=False,
            anchor=anchor,
            num_before=num_before,
            num_after=num_after,
        )

    @staticmethod
    async def _fetch(
        db: AsyncSession,
        channel_id: int,
        topic_id: Optional[int],
        general_only: bool,
        anchor: int,
        num_before: int,
        num_after: int,
    ) -> List[Dict[str, Any]]:
        """Internal: fetch messages with anchor-based pagination."""
        num_before = min(num_before, MAX_PAGE_SIZE)
        num_after = min(num_after, MAX_PAGE_SIZE)

        base_filter = [
            ChatMessage.channel_id == channel_id,
            ChatMessage.is_deleted.is_(False),
        ]
        if general_only:
            base_filter.append(ChatMessage.topic_id.is_(None))
        elif topic_id is not None:
            base_filter.append(ChatMessage.topic_id == topic_id)

        messages: List[ChatMessage] = []

        if num_before > 0:
            stmt = select(ChatMessage).options(joinedload(ChatMessage.sender)).where(*base_filter)
            if anchor > 0:
                stmt = stmt.where(ChatMessage.id < anchor)
            stmt = stmt.order_by(ChatMessage.id.desc()).limit(num_before)
            result = await db.execute(stmt)
            messages.extend(reversed(result.unique().scalars().all()))

        if num_after > 0 and anchor > 0:
            stmt = (
                select(ChatMessage)
                .options(joinedload(ChatMessage.sender))
                .where(*base_filter, ChatMessage.id >= anchor)
                .order_by(ChatMessage.id.asc())
                .limit(num_after)
            )
            result = await db.execute(stmt)
            messages.extend(result.unique().scalars().all())

        return [_format_message(m) for m in messages]

    @staticmethod
    async def search_messages(
        db: AsyncSession,
        channel_id: int,
        text: str,
        topic_id: Optional[int] = None,
        limit: int = 40,
    ) -> List[Dict[str, Any]]:
        """Search within one channel, optionally scoped to a topic.

        On PostgreSQL, uses ``to_tsvector`` / ``plainto_tsquery`` with optional
        GIN index; otherwise falls back to ``ILIKE`` substring.
        """
        match = message_fts.channel_content_match(
            db,
            ChatMessage.content,
            text,
            limit,
        )
        if match is None:
            return []
        pred, rank_expr, lim = match
        filters = [
            ChatMessage.channel_id == channel_id,
            ChatMessage.is_deleted.is_(False),
            pred,
        ]
        if topic_id is not None:
            filters.append(ChatMessage.topic_id == topic_id)

        stmt = select(ChatMessage).options(joinedload(ChatMessage.sender)).where(*filters)
        if rank_expr is not None:
            stmt = stmt.order_by(rank_expr.desc(), ChatMessage.id.desc()).limit(lim)
        else:
            stmt = stmt.order_by(ChatMessage.id.desc()).limit(lim)
        result = await db.execute(stmt)
        rows = result.unique().scalars().all()
        return [_format_message(m) for m in reversed(rows)]

    @staticmethod
    async def send_message(
        db: AsyncSession,
        channel_id: int,
        sender_id: int,
        content: str,
        topic_id: Optional[int] = None,
        message_type: str = "text",
        parent_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send a message to a channel or topic."""
        row = await db.execute(select(User).where(User.id == sender_id))
        sender = row.scalar_one_or_none()
        if not sender:
            raise ValueError("Sender not found")
        ch_row = await db.execute(select(ChatChannel).where(ChatChannel.id == channel_id))
        channel = ch_row.scalar_one_or_none()
        org_id = channel.organization_id if channel else None
        mention_ids = await resolve_mentioned_user_ids(
            db,
            sender,
            org_id,
            content[:MAX_CONTENT_LENGTH],
        )
        msg = ChatMessage(
            channel_id=channel_id,
            topic_id=topic_id,
            sender_id=sender_id,
            content=content[:MAX_CONTENT_LENGTH],
            message_type=message_type,
            parent_id=parent_id,
            mentioned_user_ids=mention_ids or None,
        )
        db.add(msg)
        await db.flush()

        if topic_id:
            t_row = await db.execute(select(ChatTopic).where(ChatTopic.id == topic_id))
            topic = t_row.scalar_one_or_none()
            if topic:
                topic.updated_at = datetime.now(UTC)

        await db.commit()
        await db.refresh(msg)

        return {
            "id": msg.id,
            "channel_id": msg.channel_id,
            "topic_id": msg.topic_id,
            "sender_id": msg.sender_id,
            "sender_name": sender.name if sender else f"User {sender_id}",
            "sender_avatar": sender.avatar if sender else None,
            "content": msg.content,
            "message_type": msg.message_type,
            "parent_id": msg.parent_id,
            "mentioned_user_ids": list(msg.mentioned_user_ids or []),
            "created_at": msg.created_at.isoformat(),
        }

    @staticmethod
    async def edit_message(
        db: AsyncSession,
        message_id: int,
        sender_id: int,
        new_content: str,
    ) -> Optional[Dict[str, Any]]:
        """Edit a message (sender only)."""
        row = await db.execute(
            select(ChatMessage)
            .options(
                joinedload(ChatMessage.channel),
                joinedload(ChatMessage.sender),
            )
            .where(
                ChatMessage.id == message_id,
                ChatMessage.sender_id == sender_id,
            )
        )
        msg = row.unique().scalar_one_or_none()
        if not msg:
            return None
        sender = msg.sender
        if not sender:
            return None
        org_id = msg.channel.organization_id if msg.channel else None
        mention_ids = await resolve_mentioned_user_ids(
            db,
            sender,
            org_id,
            new_content[:MAX_CONTENT_LENGTH],
        )
        msg.content = new_content[:MAX_CONTENT_LENGTH]
        msg.mentioned_user_ids = mention_ids or None
        msg.edited_at = datetime.now(UTC)
        await db.commit()
        refreshed = await db.execute(
            select(ChatMessage).options(joinedload(ChatMessage.sender)).where(ChatMessage.id == message_id)
        )
        msg = refreshed.unique().scalar_one_or_none()
        return _format_message(msg)

    @staticmethod
    async def delete_message(
        db: AsyncSession,
        message_id: int,
        user: User,
    ) -> bool:
        """Soft-delete a message (sender or channel moderator, Zulip-style)."""
        result = await db.execute(
            select(ChatMessage)
            .options(joinedload(ChatMessage.channel))
            .where(
                ChatMessage.id == message_id,
                ChatMessage.is_deleted.is_(False),
            )
        )
        msg = result.unique().scalar_one_or_none()
        if not msg:
            return False
        if msg.sender_id != user.id:
            channel = msg.channel
            if not channel or not can_moderate_workshop_channel(user, channel):
                return False
        msg.is_deleted = True
        await db.commit()
        return True

    @staticmethod
    async def update_last_read(
        db: AsyncSession,
        channel_id: int,
        user_id: int,
        message_id: int,
    ) -> None:
        """Update last_read_message_id for a channel member."""
        row = await db.execute(
            select(ChannelMember).where(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user_id,
            )
        )
        member = row.scalar_one_or_none()
        if member and (member.last_read_message_id is None or message_id > member.last_read_message_id):
            member.last_read_message_id = message_id
            await db.commit()


message_service = MessageService()
