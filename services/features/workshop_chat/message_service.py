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
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

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
    def get_channel_messages(
        db: Session, channel_id: int,
        anchor: int = 0, num_before: int = DEFAULT_PAGE_SIZE, num_after: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get general channel messages (topic_id is NULL), anchor-based."""
        return MessageService._fetch(
            db, channel_id=channel_id, topic_id=None,
            general_only=True, anchor=anchor,
            num_before=num_before, num_after=num_after,
        )

    @staticmethod
    def get_topic_messages(
        db: Session, topic_id: int, channel_id: int,
        anchor: int = 0, num_before: int = DEFAULT_PAGE_SIZE, num_after: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get messages for a specific topic, anchor-based."""
        return MessageService._fetch(
            db, channel_id=channel_id, topic_id=topic_id,
            general_only=False, anchor=anchor,
            num_before=num_before, num_after=num_after,
        )

    @staticmethod
    def _fetch(
        db: Session, channel_id: int, topic_id: Optional[int],
        general_only: bool, anchor: int, num_before: int, num_after: int,
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
            before_q = (
                db.query(ChatMessage)
                .options(joinedload(ChatMessage.sender))
                .filter(*base_filter)
            )
            if anchor > 0:
                before_q = before_q.filter(ChatMessage.id < anchor)
            before_q = before_q.order_by(ChatMessage.id.desc()).limit(num_before)
            messages.extend(reversed(before_q.all()))

        if num_after > 0 and anchor > 0:
            after_q = (
                db.query(ChatMessage)
                .options(joinedload(ChatMessage.sender))
                .filter(*base_filter, ChatMessage.id >= anchor)
                .order_by(ChatMessage.id.asc())
                .limit(num_after)
                .all()
            )
            messages.extend(after_q)

        return [_format_message(m) for m in messages]

    @staticmethod
    def search_messages(
        db: Session,
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
            db, ChatMessage.content, text, limit,
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

        query = (
            db.query(ChatMessage)
            .options(joinedload(ChatMessage.sender))
            .filter(*filters)
        )
        if rank_expr is not None:
            rows = (
                query.order_by(rank_expr.desc(), ChatMessage.id.desc())
                .limit(lim)
                .all()
            )
        else:
            rows = (
                query.order_by(ChatMessage.id.desc())
                .limit(lim)
                .all()
            )
        return [_format_message(m) for m in reversed(rows)]

    @staticmethod
    def send_message(
        db: Session, channel_id: int, sender_id: int, content: str,
        topic_id: Optional[int] = None, message_type: str = "text",
        parent_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send a message to a channel or topic."""
        sender = db.query(User).filter(User.id == sender_id).first()
        if not sender:
            raise ValueError("Sender not found")
        channel = db.query(ChatChannel).filter(ChatChannel.id == channel_id).first()
        org_id = channel.organization_id if channel else None
        mention_ids = resolve_mentioned_user_ids(
            db, sender, org_id, content[:MAX_CONTENT_LENGTH],
        )
        msg = ChatMessage(
            channel_id=channel_id, topic_id=topic_id,
            sender_id=sender_id, content=content[:MAX_CONTENT_LENGTH],
            message_type=message_type, parent_id=parent_id,
            mentioned_user_ids=mention_ids or None,
        )
        db.add(msg)
        db.flush()

        if topic_id:
            topic = db.query(ChatTopic).filter(ChatTopic.id == topic_id).first()
            if topic:
                topic.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(msg)

        return {
            "id": msg.id, "channel_id": msg.channel_id,
            "topic_id": msg.topic_id, "sender_id": msg.sender_id,
            "sender_name": sender.name if sender else f"User {sender_id}",
            "sender_avatar": sender.avatar if sender else None,
            "content": msg.content, "message_type": msg.message_type,
            "parent_id": msg.parent_id,
            "mentioned_user_ids": list(msg.mentioned_user_ids or []),
            "created_at": msg.created_at.isoformat(),
        }

    @staticmethod
    def edit_message(
        db: Session, message_id: int, sender_id: int, new_content: str,
    ) -> Optional[Dict[str, Any]]:
        """Edit a message (sender only)."""
        msg = (
            db.query(ChatMessage)
            .options(joinedload(ChatMessage.channel), joinedload(ChatMessage.sender))
            .filter(ChatMessage.id == message_id, ChatMessage.sender_id == sender_id)
            .first()
        )
        if not msg:
            return None
        sender = msg.sender
        if not sender:
            return None
        org_id = msg.channel.organization_id if msg.channel else None
        mention_ids = resolve_mentioned_user_ids(
            db, sender, org_id, new_content[:MAX_CONTENT_LENGTH],
        )
        msg.content = new_content[:MAX_CONTENT_LENGTH]
        msg.mentioned_user_ids = mention_ids or None
        msg.edited_at = datetime.utcnow()
        db.commit()
        db.refresh(msg)
        return _format_message(msg)

    @staticmethod
    def delete_message(db: Session, message_id: int, sender_id: int) -> bool:
        """Soft-delete a message (sender only)."""
        msg = (
            db.query(ChatMessage)
            .filter(ChatMessage.id == message_id, ChatMessage.sender_id == sender_id)
            .first()
        )
        if not msg:
            return False
        msg.is_deleted = True
        db.commit()
        return True

    @staticmethod
    def update_last_read(
        db: Session, channel_id: int, user_id: int, message_id: int,
    ) -> None:
        """Update last_read_message_id for a channel member."""
        member = (
            db.query(ChannelMember)
            .filter(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user_id,
            )
            .first()
        )
        if member and (
            member.last_read_message_id is None
            or message_id > member.last_read_message_id
        ):
            member.last_read_message_id = message_id
            db.commit()


message_service = MessageService()
