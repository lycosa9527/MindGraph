"""
Direct Message Service
========================

1:1 private message operations.

Analogous to Zulip's private-message handling in
``zerver/actions/message_send.py`` (the ``internal_prep_private_message``
path), extracted into its own module for clarity.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Any, Dict, List

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.workshop_chat import DirectMessage
from services.features.workshop_chat.mention_resolution import (
    resolve_mentioned_user_ids,
)
from services.features.workshop_chat.message_fts import dm_content_match

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
MAX_CONTENT_LENGTH = 5000


class DirectMessageService:
    """1:1 direct message operations."""

    @staticmethod
    async def list_conversations(
        db: AsyncSession,
        user_id: int,
    ) -> List[Dict[str, Any]]:
        """List DM conversations with last message and unread count.

        One grouped query for aggregates + join for last row preview (not O(n)).
        """
        other_party = case(
            (DirectMessage.sender_id == user_id, DirectMessage.recipient_id),
            else_=DirectMessage.sender_id,
        ).label("partner_id")

        pair_scope = and_(
            or_(
                DirectMessage.sender_id == user_id,
                DirectMessage.recipient_id == user_id,
            ),
            DirectMessage.is_deleted.is_(False),
        )

        agg = (
            select(
                other_party,
                func.max(DirectMessage.id).label("last_msg_id"),
                func.sum(
                    case(
                        (
                            and_(
                                DirectMessage.recipient_id == user_id,
                                DirectMessage.is_read.is_(False),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("unread_count"),
            )
            .where(pair_scope)
            .group_by(other_party)
            .subquery()
        )

        stmt = (
            select(
                agg.c.partner_id,
                agg.c.unread_count,
                DirectMessage.content,
                DirectMessage.created_at,
                DirectMessage.sender_id,
                User.name,
                User.avatar,
            )
            .join(DirectMessage, DirectMessage.id == agg.c.last_msg_id)
            .outerjoin(User, User.id == agg.c.partner_id)
        )
        result = await db.execute(stmt)
        rows = result.all()

        conversations: List[Dict[str, Any]] = []
        for row in rows:
            partner_id = int(row.partner_id)
            last = row.content
            created = row.created_at
            sender_sid = row.sender_id
            conversations.append(
                {
                    "partner_id": partner_id,
                    "partner_name": row.name if row.name else f"User {partner_id}",
                    "partner_avatar": row.avatar if row.avatar else None,
                    "last_message": {
                        "content": last[:100] if last else None,
                        "created_at": created.isoformat() if created else None,
                        "is_mine": sender_sid == user_id if sender_sid is not None else False,
                    },
                    "unread_count": int(row.unread_count or 0),
                }
            )

        conversations.sort(
            key=lambda c: c["last_message"]["created_at"] or "",
            reverse=True,
        )
        return conversations

    @staticmethod
    async def get_messages(
        db: AsyncSession,
        user_id: int,
        partner_id: int,
        anchor: int = 0,
        num_before: int = DEFAULT_PAGE_SIZE,
        num_after: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get DM messages between two users, anchor-based (like channel history)."""
        num_before = min(num_before, MAX_PAGE_SIZE)
        num_after = min(num_after, MAX_PAGE_SIZE)
        pair_filter = or_(
            (DirectMessage.sender_id == user_id) & (DirectMessage.recipient_id == partner_id),
            (DirectMessage.sender_id == partner_id) & (DirectMessage.recipient_id == user_id),
        )
        messages: List[DirectMessage] = []

        if num_before > 0:
            stmt = select(DirectMessage).where(
                pair_filter,
                DirectMessage.is_deleted.is_(False),
            )
            if anchor > 0:
                stmt = stmt.where(DirectMessage.id < anchor)
            stmt = stmt.order_by(DirectMessage.id.desc()).limit(num_before)
            result = await db.execute(stmt)
            messages.extend(reversed(result.scalars().all()))

        if num_after > 0 and anchor > 0:
            stmt = (
                select(DirectMessage)
                .where(
                    pair_filter,
                    DirectMessage.is_deleted.is_(False),
                    DirectMessage.id >= anchor,
                )
                .order_by(DirectMessage.id.asc())
                .limit(num_after)
            )
            result = await db.execute(stmt)
            messages.extend(result.scalars().all())

        return [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "recipient_id": m.recipient_id,
                "content": m.content,
                "message_type": m.message_type,
                "is_read": m.is_read,
                "mentioned_user_ids": list(m.mentioned_user_ids or []),
                "created_at": m.created_at.isoformat(),
                "edited_at": m.edited_at.isoformat() if m.edited_at else None,
            }
            for m in messages
        ]

    @staticmethod
    async def search_messages(
        db: AsyncSession,
        user_id: int,
        partner_id: int,
        text: str,
        limit: int = 40,
    ) -> List[Dict[str, Any]]:
        """DM narrow search: same pair filter as history; FTS on PG else ILIKE."""
        match = dm_content_match(
            db,
            DirectMessage.content,
            text,
            limit,
        )
        if match is None:
            return []
        pred, rank_expr, lim = match
        pair_filter = or_(
            (DirectMessage.sender_id == user_id) & (DirectMessage.recipient_id == partner_id),
            (DirectMessage.sender_id == partner_id) & (DirectMessage.recipient_id == user_id),
        )
        stmt = select(DirectMessage).where(
            pair_filter,
            DirectMessage.is_deleted.is_(False),
            pred,
        )
        if rank_expr is not None:
            stmt = stmt.order_by(rank_expr.desc(), DirectMessage.id.desc()).limit(lim)
        else:
            stmt = stmt.order_by(DirectMessage.id.desc()).limit(lim)
        result = await db.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "recipient_id": m.recipient_id,
                "content": m.content,
                "message_type": m.message_type,
                "is_read": m.is_read,
                "mentioned_user_ids": list(m.mentioned_user_ids or []),
                "created_at": m.created_at.isoformat(),
                "edited_at": m.edited_at.isoformat() if m.edited_at else None,
            }
            for m in reversed(rows)
        ]

    @staticmethod
    async def send(
        db: AsyncSession,
        sender_id: int,
        recipient_id: int,
        content: str,
        message_type: str = "text",
    ) -> Dict[str, Any]:
        """Send a direct message."""
        row = await db.execute(select(User).where(User.id == sender_id))
        sender = row.scalar_one_or_none()
        if not sender:
            raise ValueError("Sender not found")
        org_id = sender.organization_id
        mention_ids = await resolve_mentioned_user_ids(
            db,
            sender,
            org_id,
            content[:MAX_CONTENT_LENGTH],
        )
        msg = DirectMessage(
            sender_id=sender_id,
            recipient_id=recipient_id,
            content=content[:MAX_CONTENT_LENGTH],
            message_type=message_type,
            mentioned_user_ids=mention_ids or None,
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)

        return {
            "id": msg.id,
            "sender_id": msg.sender_id,
            "sender_name": sender.name if sender else f"User {sender_id}",
            "sender_avatar": sender.avatar if sender else None,
            "recipient_id": msg.recipient_id,
            "content": msg.content,
            "message_type": msg.message_type,
            "is_read": msg.is_read,
            "mentioned_user_ids": list(msg.mentioned_user_ids or []),
            "created_at": msg.created_at.isoformat(),
        }

    @staticmethod
    async def mark_read(
        db: AsyncSession,
        user_id: int,
        partner_id: int,
    ) -> int:
        """Mark all DMs from partner as read. Returns count updated."""
        result = await db.execute(
            update(DirectMessage)
            .where(
                DirectMessage.sender_id == partner_id,
                DirectMessage.recipient_id == user_id,
                DirectMessage.is_read.is_(False),
            )
            .values(is_read=True)
        )
        await db.commit()
        return result.rowcount


dm_service = DirectMessageService()
