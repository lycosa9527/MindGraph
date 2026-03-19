"""
Topic Service
===============

Topic (conversation thread) lifecycle operations.

Topics are now lightweight labels within a channel, matching Zulip's
concept.  Heavyweight metadata (status, deadline, diagram) has moved
to the parent ``ChatChannel``.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.domain.workshop_chat import (
    ChatTopic, ChatMessage, UserTopicPreference,
)

logger = logging.getLogger(__name__)

MAX_TOPIC_TITLE_LENGTH = 200


class TopicService:
    """Lightweight topic (conversation) operations."""

    @staticmethod
    def list_topics(
        db: Session,
        channel_id: int,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """List topics in a channel with message counts."""
        topics = (
            db.query(ChatTopic)
            .filter(ChatTopic.channel_id == channel_id)
            .order_by(ChatTopic.updated_at.desc())
            .all()
        )

        return [TopicService._format_topic(db, t, user_id) for t in topics]

    @staticmethod
    def _format_topic(
        db: Session,
        topic: ChatTopic,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Format a topic with message count and user preference."""
        msg_count = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.topic_id == topic.id,
                ChatMessage.is_deleted.is_(False),
            )
            .count()
        )

        visibility_policy = "inherit"
        if user_id:
            pref = (
                db.query(UserTopicPreference)
                .filter(
                    UserTopicPreference.user_id == user_id,
                    UserTopicPreference.topic_id == topic.id,
                )
                .first()
            )
            if pref:
                visibility_policy = pref.visibility_policy

        return {
            "id": topic.id,
            "channel_id": topic.channel_id,
            "title": topic.title,
            "description": topic.description,
            "created_by": topic.created_by,
            "creator_name": topic.creator.name if topic.creator else None,
            "visibility_policy": visibility_policy,
            "message_count": msg_count,
            "created_at": topic.created_at.isoformat(),
            "updated_at": topic.updated_at.isoformat(),
        }

    @staticmethod
    def create_topic(
        db: Session,
        channel_id: int,
        title: str,
        created_by: int,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a topic (conversation) within a channel."""
        topic = ChatTopic(
            channel_id=channel_id,
            title=title[:MAX_TOPIC_TITLE_LENGTH],
            description=description,
            created_by=created_by,
        )
        db.add(topic)
        db.commit()
        logger.info(
            "[WorkshopChat] Topic '%s' created in channel %d by user %d",
            title, channel_id, created_by,
        )
        return {
            "id": topic.id, "channel_id": topic.channel_id,
            "title": topic.title, "description": topic.description,
            "created_by": topic.created_by,
            "created_at": topic.created_at.isoformat(),
        }

    @staticmethod
    def update_topic(
        db: Session,
        topic_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update topic title or description."""
        topic = db.query(ChatTopic).filter(ChatTopic.id == topic_id).first()
        if not topic:
            return None

        if title is not None:
            topic.title = title[:MAX_TOPIC_TITLE_LENGTH]
        if description is not None:
            topic.description = description

        topic.updated_at = datetime.utcnow()
        db.commit()
        return {
            "id": topic.id, "channel_id": topic.channel_id,
            "title": topic.title, "description": topic.description,
            "updated_at": topic.updated_at.isoformat(),
        }

    @staticmethod
    def get_topic(db: Session, topic_id: int) -> Optional[ChatTopic]:
        """Get a topic by ID."""
        return db.query(ChatTopic).filter(ChatTopic.id == topic_id).first()

    @staticmethod
    def move_topic(
        db: Session, topic_id: int, target_channel_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Move a topic (and its messages) to a different channel."""
        topic = db.query(ChatTopic).filter(ChatTopic.id == topic_id).first()
        if not topic:
            return None
        old_channel = topic.channel_id
        topic.channel_id = target_channel_id
        topic.updated_at = datetime.utcnow()

        db.query(ChatMessage).filter(
            ChatMessage.topic_id == topic_id,
        ).update({"channel_id": target_channel_id}, synchronize_session=False)

        db.commit()
        logger.info(
            "[WorkshopChat] Topic %d moved from channel %d to %d",
            topic_id, old_channel, target_channel_id,
        )
        return {
            "id": topic.id,
            "channel_id": topic.channel_id,
            "old_channel_id": old_channel,
        }

    @staticmethod
    def delete_topic(db: Session, topic_id: int) -> bool:
        """Hard-delete a topic and its messages (cascade)."""
        topic = db.query(ChatTopic).filter(ChatTopic.id == topic_id).first()
        if not topic:
            return False
        db.delete(topic)
        db.commit()
        logger.info("[WorkshopChat] Topic %d deleted", topic_id)
        return True

    # ── Mark as read ─────────────────────────────────────────────

    @staticmethod
    def mark_topic_read(
        db: Session, topic_id: int, user_id: int,
    ) -> Dict[str, Any]:
        """Update the user topic preference to mark as read."""
        pref = (
            db.query(UserTopicPreference)
            .filter(
                UserTopicPreference.user_id == user_id,
                UserTopicPreference.topic_id == topic_id,
            )
            .first()
        )
        if not pref:
            pref = UserTopicPreference(
                user_id=user_id,
                topic_id=topic_id,
                visibility_policy="inherit",
            )
            db.add(pref)
        pref.last_updated = datetime.utcnow()
        db.commit()
        return {"topic_id": topic_id, "marked_read": True}

    # ── User topic visibility preferences ────────────────────────

    @staticmethod
    def set_visibility(
        db: Session,
        topic_id: int,
        user_id: int,
        policy: str,
    ) -> Dict[str, Any]:
        """Set user visibility policy for a topic.

        Valid policies: inherit, muted, unmuted, followed.
        """
        valid = {"inherit", "muted", "unmuted", "followed"}
        if policy not in valid:
            raise ValueError(f"Invalid policy: {policy}")

        pref = (
            db.query(UserTopicPreference)
            .filter(
                UserTopicPreference.user_id == user_id,
                UserTopicPreference.topic_id == topic_id,
            )
            .first()
        )
        if not pref:
            pref = UserTopicPreference(
                user_id=user_id,
                topic_id=topic_id,
                visibility_policy=policy,
            )
            db.add(pref)
        else:
            pref.visibility_policy = policy
            pref.last_updated = datetime.utcnow()
        db.commit()
        return {
            "topic_id": topic_id,
            "visibility_policy": pref.visibility_policy,
        }

    @staticmethod
    def rename_topic(
        db: Session, topic_id: int, new_title: str,
    ) -> Optional[Dict[str, Any]]:
        """Rename a topic."""
        topic = db.query(ChatTopic).filter(ChatTopic.id == topic_id).first()
        if not topic:
            return None
        topic.title = new_title[:MAX_TOPIC_TITLE_LENGTH]
        topic.updated_at = datetime.utcnow()
        db.commit()
        logger.info("[WorkshopChat] Topic %d renamed to '%s'", topic_id, new_title)
        return {"id": topic.id, "title": topic.title}


topic_service = TopicService()
