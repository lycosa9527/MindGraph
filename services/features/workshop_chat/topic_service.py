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
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.functions import count as sql_count

from models.domain.workshop_chat import (
    ChannelMember,
    ChatMessage,
    ChatTopic,
    UserTopicPreference,
)

logger = logging.getLogger(__name__)

MAX_TOPIC_TITLE_LENGTH = 200


class TopicService:
    """Lightweight topic (conversation) operations."""

    @staticmethod
    async def list_topics(
        db: AsyncSession,
        channel_id: int,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """List topics in a channel with message counts.

        Topics without a ``UserTopicPreference`` row use the channel read
        waterline (``ChannelMember.last_read_message_id``): only messages with
        id above that cursor count as unread, matching channel-level catch-up.
        """
        result = await db.execute(
            select(ChatTopic)
            .options(selectinload(ChatTopic.creator))
            .where(ChatTopic.channel_id == channel_id)
            .order_by(ChatTopic.updated_at.desc())
        )
        topics = result.scalars().all()
        if not topics:
            return []

        topic_ids = [topic.id for topic in topics]
        (
            _,
            msg_counts,
            prefs,
            unread_pref_map,
            unread_no_pref_map,
        ) = await TopicService._topic_list_batch_data(
            db,
            channel_id,
            user_id,
            topic_ids,
        )

        return [
            TopicService._topic_row_dict(
                topic,
                msg_count=msg_counts.get(topic.id, 0),
                unread_count=TopicService._topic_unread_from_maps(
                    topic.id,
                    msg_count=msg_counts.get(topic.id, 0),
                    has_pref=topic.id in prefs,
                    unread_pref_map=unread_pref_map,
                    unread_no_pref_map=unread_no_pref_map,
                ),
                visibility_policy=(prefs[topic.id].visibility_policy if topic.id in prefs else "inherit"),
            )
            for topic in topics
        ]

    @staticmethod
    async def _topic_list_batch_data(
        db: AsyncSession,
        channel_id: int,
        user_id: Optional[int],
        topic_ids: List[int],
    ) -> Tuple[
        int,
        Dict[int, int],
        Dict[int, UserTopicPreference],
        Dict[int, int],
        Dict[int, int],
    ]:
        waterline = 0
        if user_id:
            result = await db.execute(
                select(ChannelMember).where(
                    ChannelMember.channel_id == channel_id,
                    ChannelMember.user_id == user_id,
                )
            )
            member = result.scalar_one_or_none()
            if member and member.last_read_message_id:
                waterline = int(member.last_read_message_id)

        mc_result = await db.execute(
            select(ChatMessage.topic_id, sql_count(ChatMessage.id))
            .where(
                ChatMessage.topic_id.in_(topic_ids),
                ChatMessage.is_deleted.is_(False),
            )
            .group_by(ChatMessage.topic_id)
        )
        msg_counts = dict(mc_result.all())

        prefs: Dict[int, UserTopicPreference] = {}
        if user_id:
            pref_result = await db.execute(
                select(UserTopicPreference).where(
                    UserTopicPreference.user_id == user_id,
                    UserTopicPreference.topic_id.in_(topic_ids),
                )
            )
            for row in pref_result.scalars().all():
                prefs[row.topic_id] = row

        unread_pref_map: Dict[int, int] = {}
        if user_id and prefs:
            unread_pref_result = await db.execute(
                select(
                    ChatMessage.topic_id,
                    sql_count(ChatMessage.id),
                )
                .join(
                    UserTopicPreference,
                    and_(
                        UserTopicPreference.topic_id == ChatMessage.topic_id,
                        UserTopicPreference.user_id == user_id,
                    ),
                )
                .where(
                    ChatMessage.topic_id.in_(list(prefs.keys())),
                    ChatMessage.is_deleted.is_(False),
                    ChatMessage.created_at > UserTopicPreference.last_updated,
                )
                .group_by(ChatMessage.topic_id)
            )
            unread_pref_map = dict(unread_pref_result.all())

        topic_ids_no_pref = [tid for tid in topic_ids if tid not in prefs]
        unread_no_pref_map: Dict[int, int] = {}
        if topic_ids_no_pref:
            no_pref_result = await db.execute(
                select(ChatMessage.topic_id, sql_count(ChatMessage.id))
                .where(
                    ChatMessage.topic_id.in_(topic_ids_no_pref),
                    ChatMessage.is_deleted.is_(False),
                    ChatMessage.id > waterline,
                )
                .group_by(ChatMessage.topic_id)
            )
            unread_no_pref_map = dict(no_pref_result.all())

        return (
            waterline,
            msg_counts,
            prefs,
            unread_pref_map,
            unread_no_pref_map,
        )

    @staticmethod
    def _topic_unread_from_maps(
        topic_id: int,
        msg_count: int,
        has_pref: bool,
        unread_pref_map: Dict[int, int],
        unread_no_pref_map: Dict[int, int],
    ) -> int:
        if msg_count == 0:
            return 0
        if has_pref:
            return int(unread_pref_map.get(topic_id, 0))
        return int(unread_no_pref_map.get(topic_id, 0))

    @staticmethod
    def _topic_row_dict(
        topic: ChatTopic,
        msg_count: int,
        unread_count: int,
        visibility_policy: str,
    ) -> Dict[str, Any]:
        return {
            "id": topic.id,
            "channel_id": topic.channel_id,
            "title": topic.title,
            "description": topic.description,
            "created_by": topic.created_by,
            "creator_name": topic.creator.name if topic.creator else None,
            "visibility_policy": visibility_policy,
            "message_count": msg_count,
            "unread_count": unread_count,
            "created_at": topic.created_at.isoformat(),
            "updated_at": topic.updated_at.isoformat(),
        }

    @staticmethod
    async def create_topic(
        db: AsyncSession,
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
        await db.commit()
        logger.info(
            "[WorkshopChat] Topic '%s' created in channel %d by user %d",
            title,
            channel_id,
            created_by,
        )
        return {
            "id": topic.id,
            "channel_id": topic.channel_id,
            "title": topic.title,
            "description": topic.description,
            "created_by": topic.created_by,
            "created_at": topic.created_at.isoformat(),
        }

    @staticmethod
    async def update_topic(
        db: AsyncSession,
        topic_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update topic title or description."""
        result = await db.execute(select(ChatTopic).where(ChatTopic.id == topic_id))
        topic = result.scalar_one_or_none()
        if not topic:
            return None

        if title is not None:
            topic.title = title[:MAX_TOPIC_TITLE_LENGTH]
        if description is not None:
            topic.description = description

        topic.updated_at = datetime.now(UTC)
        await db.commit()
        return {
            "id": topic.id,
            "channel_id": topic.channel_id,
            "title": topic.title,
            "description": topic.description,
            "updated_at": topic.updated_at.isoformat(),
        }

    @staticmethod
    async def get_topic(
        db: AsyncSession,
        topic_id: int,
    ) -> Optional[ChatTopic]:
        """Get a topic by ID."""
        result = await db.execute(select(ChatTopic).where(ChatTopic.id == topic_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def move_topic(
        db: AsyncSession,
        topic_id: int,
        target_channel_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Move a topic (and its messages) to a different channel."""
        result = await db.execute(select(ChatTopic).where(ChatTopic.id == topic_id))
        topic = result.scalar_one_or_none()
        if not topic:
            return None
        old_channel = topic.channel_id
        topic.channel_id = target_channel_id
        topic.updated_at = datetime.now(UTC)

        await db.execute(
            update(ChatMessage).where(ChatMessage.topic_id == topic_id).values(channel_id=target_channel_id)
        )

        await db.commit()
        logger.info(
            "[WorkshopChat] Topic %d moved from channel %d to %d",
            topic_id,
            old_channel,
            target_channel_id,
        )
        return {
            "id": topic.id,
            "channel_id": topic.channel_id,
            "old_channel_id": old_channel,
        }

    @staticmethod
    async def delete_topic(db: AsyncSession, topic_id: int) -> bool:
        """Hard-delete a topic and its messages (cascade)."""
        result = await db.execute(select(ChatTopic).where(ChatTopic.id == topic_id))
        topic = result.scalar_one_or_none()
        if not topic:
            return False
        await db.delete(topic)
        await db.commit()
        logger.info("[WorkshopChat] Topic %d deleted", topic_id)
        return True

    # ── Mark as read ─────────────────────────────────────────────

    @staticmethod
    async def mark_topic_read(
        db: AsyncSession,
        topic_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """Update topic read state and advance channel last-read waterline.

        Channel-level ``unread_count`` uses ``ChannelMember.last_read_message_id``.
        Advancing it to the latest message id in this topic clears those messages
        from the channel aggregate while per-topic unreads use ``last_updated``.
        """
        result = await db.execute(select(ChatTopic).where(ChatTopic.id == topic_id))
        topic = result.scalar_one_or_none()
        if not topic:
            return {"topic_id": topic_id, "marked_read": False}

        pref_result = await db.execute(
            select(UserTopicPreference).where(
                UserTopicPreference.user_id == user_id,
                UserTopicPreference.topic_id == topic_id,
            )
        )
        pref = pref_result.scalar_one_or_none()
        if not pref:
            pref = UserTopicPreference(
                user_id=user_id,
                topic_id=topic_id,
                visibility_policy="inherit",
            )
            db.add(pref)
        pref.last_updated = datetime.now(UTC)

        max_result = await db.execute(
            select(func.max(ChatMessage.id)).where(
                ChatMessage.topic_id == topic_id,
                ChatMessage.is_deleted.is_(False),
            )
        )
        max_msg_id = max_result.scalar()
        if max_msg_id:
            member_result = await db.execute(
                select(ChannelMember).where(
                    ChannelMember.channel_id == topic.channel_id,
                    ChannelMember.user_id == user_id,
                )
            )
            member = member_result.scalar_one_or_none()
            if member:
                current = member.last_read_message_id or 0
                if max_msg_id > current:
                    member.last_read_message_id = max_msg_id

        await db.commit()
        return {"topic_id": topic_id, "marked_read": True}

    # ── User topic visibility preferences ────────────────────────

    @staticmethod
    async def set_visibility(
        db: AsyncSession,
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

        result = await db.execute(
            select(UserTopicPreference).where(
                UserTopicPreference.user_id == user_id,
                UserTopicPreference.topic_id == topic_id,
            )
        )
        pref = result.scalar_one_or_none()
        if not pref:
            pref = UserTopicPreference(
                user_id=user_id,
                topic_id=topic_id,
                visibility_policy=policy,
            )
            db.add(pref)
        else:
            pref.visibility_policy = policy
            pref.last_updated = datetime.now(UTC)
        await db.commit()
        return {
            "topic_id": topic_id,
            "visibility_policy": pref.visibility_policy,
        }

    @staticmethod
    async def rename_topic(
        db: AsyncSession,
        topic_id: int,
        new_title: str,
    ) -> Optional[Dict[str, Any]]:
        """Rename a topic."""
        result = await db.execute(select(ChatTopic).where(ChatTopic.id == topic_id))
        topic = result.scalar_one_or_none()
        if not topic:
            return None
        topic.title = new_title[:MAX_TOPIC_TITLE_LENGTH]
        topic.updated_at = datetime.now(UTC)
        await db.commit()
        logger.info(
            "[WorkshopChat] Topic %d renamed to '%s'",
            topic_id,
            new_title,
        )
        return {"id": topic.id, "title": topic.title}


topic_service = TopicService()
