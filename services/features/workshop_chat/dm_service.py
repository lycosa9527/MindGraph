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

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models.domain.auth import User
from models.domain.workshop_chat import DirectMessage

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
MAX_CONTENT_LENGTH = 5000


class DirectMessageService:
    """1:1 direct message operations."""

    @staticmethod
    def list_conversations(db: Session, user_id: int) -> List[Dict[str, Any]]:
        """List DM conversations with last message and unread count."""
        partner_ids_sent = (
            db.query(DirectMessage.recipient_id)
            .filter(DirectMessage.sender_id == user_id)
            .distinct()
        )
        partner_ids_recv = (
            db.query(DirectMessage.sender_id)
            .filter(DirectMessage.recipient_id == user_id)
            .distinct()
        )
        partner_ids = {
            row[0] for row in partner_ids_sent.union(partner_ids_recv).all()
        }

        conversations = []
        for partner_id in partner_ids:
            entry = DirectMessageService._build_conversation_entry(
                db, user_id, partner_id
            )
            conversations.append(entry)

        conversations.sort(
            key=lambda c: c["last_message"]["created_at"] or "", reverse=True
        )
        return conversations

    @staticmethod
    def _build_conversation_entry(
        db: Session, user_id: int, partner_id: int,
    ) -> Dict[str, Any]:
        """Build a single conversation entry for list_conversations."""
        partner = db.query(User).filter(User.id == partner_id).first()
        pair_filter = or_(
            (DirectMessage.sender_id == user_id)
            & (DirectMessage.recipient_id == partner_id),
            (DirectMessage.sender_id == partner_id)
            & (DirectMessage.recipient_id == user_id),
        )
        last_msg = (
            db.query(DirectMessage)
            .filter(pair_filter, DirectMessage.is_deleted.is_(False))
            .order_by(DirectMessage.id.desc())
            .first()
        )
        unread = (
            db.query(DirectMessage)
            .filter(
                DirectMessage.sender_id == partner_id,
                DirectMessage.recipient_id == user_id,
                DirectMessage.is_read.is_(False),
                DirectMessage.is_deleted.is_(False),
            )
            .count()
        )
        return {
            "partner_id": partner_id,
            "partner_name": partner.name if partner else f"User {partner_id}",
            "partner_avatar": partner.avatar if partner else None,
            "last_message": {
                "content": last_msg.content[:100] if last_msg else None,
                "created_at": last_msg.created_at.isoformat() if last_msg else None,
                "is_mine": last_msg.sender_id == user_id if last_msg else False,
            },
            "unread_count": unread,
        }

    @staticmethod
    def get_messages(
        db: Session, user_id: int, partner_id: int,
        anchor: int = 0, num_before: int = DEFAULT_PAGE_SIZE,
    ) -> List[Dict[str, Any]]:
        """Get DM messages between two users, anchor-based."""
        num_before = min(num_before, MAX_PAGE_SIZE)
        pair_filter = or_(
            (DirectMessage.sender_id == user_id)
            & (DirectMessage.recipient_id == partner_id),
            (DirectMessage.sender_id == partner_id)
            & (DirectMessage.recipient_id == user_id),
        )
        query = (
            db.query(DirectMessage)
            .filter(pair_filter, DirectMessage.is_deleted.is_(False))
        )
        if anchor > 0:
            query = query.filter(DirectMessage.id < anchor)
        messages = list(reversed(
            query.order_by(DirectMessage.id.desc()).limit(num_before).all()
        ))
        return [
            {
                "id": m.id, "sender_id": m.sender_id,
                "recipient_id": m.recipient_id, "content": m.content,
                "message_type": m.message_type, "is_read": m.is_read,
                "created_at": m.created_at.isoformat(),
                "edited_at": m.edited_at.isoformat() if m.edited_at else None,
            }
            for m in messages
        ]

    @staticmethod
    def send(
        db: Session, sender_id: int, recipient_id: int,
        content: str, message_type: str = "text",
    ) -> Dict[str, Any]:
        """Send a direct message."""
        msg = DirectMessage(
            sender_id=sender_id, recipient_id=recipient_id,
            content=content[:MAX_CONTENT_LENGTH], message_type=message_type,
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)

        sender = db.query(User).filter(User.id == sender_id).first()
        return {
            "id": msg.id, "sender_id": msg.sender_id,
            "sender_name": sender.name if sender else f"User {sender_id}",
            "sender_avatar": sender.avatar if sender else None,
            "recipient_id": msg.recipient_id, "content": msg.content,
            "message_type": msg.message_type, "is_read": msg.is_read,
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
