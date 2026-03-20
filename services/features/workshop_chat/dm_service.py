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

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

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
    def list_conversations(db: Session, user_id: int) -> List[Dict[str, Any]]:
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
            db.query(
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
            .filter(pair_scope)
            .group_by(other_party)
            .subquery()
        )

        rows = (
            db.query(
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
            .all()
        )

        conversations: List[Dict[str, Any]] = []
        for row in rows:
            partner_id = int(row.partner_id)
            last = row.content
            created = row.created_at
            sender_sid = row.sender_id
            conversations.append({
                "partner_id": partner_id,
                "partner_name": row.name if row.name else f"User {partner_id}",
                "partner_avatar": row.avatar if row.avatar else None,
                "last_message": {
                    "content": last[:100] if last else None,
                    "created_at": created.isoformat() if created else None,
                    "is_mine": sender_sid == user_id if sender_sid is not None else False,
                },
                "unread_count": int(row.unread_count or 0),
            })

        conversations.sort(
            key=lambda c: c["last_message"]["created_at"] or "", reverse=True,
        )
        return conversations

    @staticmethod
    def get_messages(
        db: Session, user_id: int, partner_id: int,
        anchor: int = 0, num_before: int = DEFAULT_PAGE_SIZE,
        num_after: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get DM messages between two users, anchor-based (like channel history)."""
        num_before = min(num_before, MAX_PAGE_SIZE)
        num_after = min(num_after, MAX_PAGE_SIZE)
        pair_filter = or_(
            (DirectMessage.sender_id == user_id)
            & (DirectMessage.recipient_id == partner_id),
            (DirectMessage.sender_id == partner_id)
            & (DirectMessage.recipient_id == user_id),
        )
        messages: List[DirectMessage] = []

        if num_before > 0:
            before_q = (
                db.query(DirectMessage)
                .filter(
                    pair_filter,
                    DirectMessage.is_deleted.is_(False),
                )
            )
            if anchor > 0:
                before_q = before_q.filter(DirectMessage.id < anchor)
            before_q = before_q.order_by(DirectMessage.id.desc()).limit(num_before)
            messages.extend(reversed(before_q.all()))

        if num_after > 0 and anchor > 0:
            after_rows = (
                db.query(DirectMessage)
                .filter(
                    pair_filter,
                    DirectMessage.is_deleted.is_(False),
                    DirectMessage.id >= anchor,
                )
                .order_by(DirectMessage.id.asc())
                .limit(num_after)
                .all()
            )
            messages.extend(after_rows)

        return [
            {
                "id": m.id, "sender_id": m.sender_id,
                "recipient_id": m.recipient_id, "content": m.content,
                "message_type": m.message_type, "is_read": m.is_read,
                "mentioned_user_ids": list(m.mentioned_user_ids or []),
                "created_at": m.created_at.isoformat(),
                "edited_at": m.edited_at.isoformat() if m.edited_at else None,
            }
            for m in messages
        ]

    @staticmethod
    def search_messages(
        db: Session,
        user_id: int,
        partner_id: int,
        text: str,
        limit: int = 40,
    ) -> List[Dict[str, Any]]:
        """DM narrow search: same pair filter as history; FTS on PG else ILIKE."""
        match = dm_content_match(
            db, DirectMessage.content, text, limit,
        )
        if match is None:
            return []
        pred, rank_expr, lim = match
        pair_filter = or_(
            (DirectMessage.sender_id == user_id)
            & (DirectMessage.recipient_id == partner_id),
            (DirectMessage.sender_id == partner_id)
            & (DirectMessage.recipient_id == user_id),
        )
        query = db.query(DirectMessage).filter(
            pair_filter,
            DirectMessage.is_deleted.is_(False),
            pred,
        )
        if rank_expr is not None:
            rows = (
                query.order_by(rank_expr.desc(), DirectMessage.id.desc())
                .limit(lim)
                .all()
            )
        else:
            rows = (
                query.order_by(DirectMessage.id.desc())
                .limit(lim)
                .all()
            )
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
    def send(
        db: Session, sender_id: int, recipient_id: int,
        content: str, message_type: str = "text",
    ) -> Dict[str, Any]:
        """Send a direct message."""
        sender = db.query(User).filter(User.id == sender_id).first()
        if not sender:
            raise ValueError("Sender not found")
        org_id = sender.organization_id
        mention_ids = resolve_mentioned_user_ids(
            db, sender, org_id, content[:MAX_CONTENT_LENGTH],
        )
        msg = DirectMessage(
            sender_id=sender_id, recipient_id=recipient_id,
            content=content[:MAX_CONTENT_LENGTH], message_type=message_type,
            mentioned_user_ids=mention_ids or None,
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)

        return {
            "id": msg.id, "sender_id": msg.sender_id,
            "sender_name": sender.name if sender else f"User {sender_id}",
            "sender_avatar": sender.avatar if sender else None,
            "recipient_id": msg.recipient_id, "content": msg.content,
            "message_type": msg.message_type, "is_read": msg.is_read,
            "mentioned_user_ids": list(msg.mentioned_user_ids or []),
            "created_at": msg.created_at.isoformat(),
        }

    @staticmethod
    def mark_read(db: Session, user_id: int, partner_id: int) -> int:
        """Mark all DMs from partner as read. Returns count updated."""
        updated = (
            db.query(DirectMessage)
            .filter(
                DirectMessage.sender_id == partner_id,
                DirectMessage.recipient_id == user_id,
                DirectMessage.is_read.is_(False),
            )
            .update({"is_read": True})
        )
        db.commit()
        return updated


dm_service = DirectMessageService()
