"""
Default Channel Seeding
=========================

Pre-configured channel groups and lesson-study channels seeded when a
school first initializes its workshop.

Hierarchy (aligned with Zulip):
  Group (parent channel, parent_id=NULL)
    └─ Lesson-Study channel (child, parent_id=group.id)
         └─ Topic (lightweight conversation thread)
              └─ Messages

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.domain.workshop_chat import (
    ChatChannel,
    ChannelMember,
    ChatMessage,
    ChatTopic,
)
from services.features.workshop_chat.seed_channel_data import (
    ANNOUNCE_CHANNEL,
    DEFAULT_CHANNEL_GROUPS,
)

logger = logging.getLogger(__name__)

SEED_MSG_INTERVAL_MINUTES = 3


# ── Seeding helpers ───────────────────────────────────────────────


def _normalize_message_content(raw: Any) -> str:
    """Ensure message content is a single string (seed data uses tuples of parts)."""
    if isinstance(raw, tuple):
        return "".join(str(part) for part in raw)
    if isinstance(raw, str):
        return raw
    return str(raw)


def _seed_topic_messages(
    db: Session,
    channel_id: int,
    topic_id: int,
    sender_id: int,
    messages: List[Any],
    base_time: datetime,
) -> None:
    """Insert filler messages for a single topic with staggered timestamps."""
    for idx, raw_content in enumerate(messages):
        content = _normalize_message_content(raw_content)
        created_at = base_time + timedelta(
            minutes=idx * SEED_MSG_INTERVAL_MINUTES,
        )
        db.add(
            ChatMessage(
                channel_id=channel_id,
                topic_id=topic_id,
                sender_id=sender_id,
                content=content,
                message_type="text",
                created_at=created_at,
            )
        )


def _seed_lesson_study_channel(
    db: Session,
    parent_id: int,
    organization_id: int,
    created_by: int,
    child_data: Dict[str, Any],
    base_time: datetime,
) -> Dict[str, Any]:
    """Create a single lesson-study channel with its topics and messages."""
    child = ChatChannel(
        name=child_data["name"],
        description=child_data.get("description"),
        organization_id=organization_id,
        created_by=created_by,
        parent_id=parent_id,
        color=child_data.get("color"),
        status=child_data.get("status", "open"),
    )
    db.add(child)
    db.flush()

    db.add(
        ChannelMember(
            channel_id=child.id,
            user_id=created_by,
            role="owner",
        )
    )

    for topic_idx, topic_data in enumerate(child_data.get("topics", [])):
        topic = ChatTopic(
            channel_id=child.id,
            title=topic_data["title"],
            description=topic_data.get("description"),
            created_by=created_by,
        )
        db.add(topic)
        db.flush()

        topic_messages = topic_data.get("messages", [])
        if topic_messages:
            topic_base = base_time + timedelta(minutes=topic_idx * 15)
            _seed_topic_messages(
                db,
                child.id,
                topic.id,
                created_by,
                topic_messages,
                topic_base,
            )

    return {
        "id": child.id,
        "name": child.name,
        "topic_count": len(child_data.get("topics", [])),
    }


# ── Seeding logic ─────────────────────────────────────────────────


def _ensure_announce_topics_and_messages(
    db: Session,
    channel: ChatChannel,
    created_by: int,
    base_time: datetime,
) -> None:
    """Add missing topics and messages to an existing announce channel."""
    existing_titles = {t.title for t in db.query(ChatTopic).filter(ChatTopic.channel_id == channel.id).all()}
    for topic_idx, topic_data in enumerate(ANNOUNCE_CHANNEL.get("topics", [])):
        title = topic_data["title"]
        if title in existing_titles:
            continue
        topic = ChatTopic(
            channel_id=channel.id,
            title=title,
            description=topic_data.get("description"),
            created_by=created_by,
        )
        db.add(topic)
        db.flush()
        topic_messages = topic_data.get("messages", [])
        if topic_messages:
            topic_base = base_time + timedelta(minutes=topic_idx * 20)
            _seed_topic_messages(
                db,
                channel.id,
                topic.id,
                created_by,
                topic_messages,
                topic_base,
            )
        existing_titles.add(title)


def _backfill_empty_announce_topic_messages(
    db: Session,
    channel: ChatChannel,
    created_by: int,
    base_time: datetime,
) -> bool:
    """Insert seed messages for announce topics that exist but have none.

    When topics were created without seed messages (or before seed data
    existed), :func:`_ensure_announce_topics_and_messages` skips them
    because the title already exists. This fills those gaps idempotently.
    """
    topic_specs = ANNOUNCE_CHANNEL.get("topics", [])
    title_to_data = {t["title"]: t for t in topic_specs}
    if not title_to_data:
        return False
    ordered_titles = [t["title"] for t in topic_specs]
    topics = db.query(ChatTopic).filter(ChatTopic.channel_id == channel.id).all()
    added = False
    for topic in topics:
        data = title_to_data.get(topic.title)
        if not data:
            continue
        msg_count = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.channel_id == channel.id,
                ChatMessage.topic_id == topic.id,
                ChatMessage.is_deleted.is_(False),
            )
            .count()
        )
        if msg_count > 0:
            continue
        topic_messages = data.get("messages", [])
        if not topic_messages:
            continue
        try:
            topic_idx = ordered_titles.index(topic.title)
        except ValueError:
            topic_idx = 0
        topic_base = base_time + timedelta(minutes=topic_idx * 20)
        _seed_topic_messages(
            db,
            channel.id,
            topic.id,
            created_by,
            topic_messages,
            topic_base,
        )
        added = True
    return added


def seed_announce_channel(
    db: Session,
    created_by: int,
) -> Optional[Dict[str, Any]]:
    """Create or top-up the global announce channel.

    The announce channel has ``organization_id = NULL`` and is visible to
    all users.  If it already exists but has no (or incomplete) topics/messages,
    we add the missing seed content so it is never left empty.
    """
    existing = db.query(ChatChannel).filter(ChatChannel.channel_type == "announce").first()
    base_time = datetime.utcnow() - timedelta(hours=2)

    if existing:
        topic_count = db.query(ChatTopic).filter(ChatTopic.channel_id == existing.id).count()
        if topic_count < len(ANNOUNCE_CHANNEL.get("topics", [])):
            _ensure_announce_topics_and_messages(
                db,
                existing,
                created_by,
                base_time,
            )
            db.commit()
            logger.info(
                "[WorkshopChat] Topped up announce channel '%s' with missing topics (user %d)",
                existing.name,
                created_by,
            )
        if _backfill_empty_announce_topic_messages(
            db,
            existing,
            created_by,
            base_time,
        ):
            db.commit()
            logger.info(
                "[WorkshopChat] Backfilled seed messages on announce channel '%s' (user %d)",
                existing.name,
                created_by,
            )
        membership = (
            db.query(ChannelMember)
            .filter(
                ChannelMember.channel_id == existing.id,
                ChannelMember.user_id == created_by,
            )
            .first()
        )
        if not membership:
            db.add(
                ChannelMember(
                    channel_id=existing.id,
                    user_id=created_by,
                    role="owner",
                )
            )
            db.commit()
        return {"id": existing.id, "name": existing.name, "channel_type": "announce"}

    channel = ChatChannel(
        name=ANNOUNCE_CHANNEL["name"],
        description=ANNOUNCE_CHANNEL["description"],
        avatar=ANNOUNCE_CHANNEL["avatar"],
        organization_id=None,
        created_by=created_by,
        channel_type="announce",
        posting_policy="managers",
    )
    db.add(channel)
    db.flush()

    db.add(
        ChannelMember(
            channel_id=channel.id,
            user_id=created_by,
            role="owner",
        )
    )

    for topic_idx, topic_data in enumerate(ANNOUNCE_CHANNEL.get("topics", [])):
        topic = ChatTopic(
            channel_id=channel.id,
            title=topic_data["title"],
            description=topic_data.get("description"),
            created_by=created_by,
        )
        db.add(topic)
        db.flush()

        topic_messages = topic_data.get("messages", [])
        if topic_messages:
            topic_base = base_time + timedelta(minutes=topic_idx * 20)
            _seed_topic_messages(
                db,
                channel.id,
                topic.id,
                created_by,
                topic_messages,
                topic_base,
            )

    db.commit()
    logger.info(
        "[WorkshopChat] Global announce channel '%s' seeded by user %d",
        channel.name,
        created_by,
    )
    return {"id": channel.id, "name": channel.name, "channel_type": "announce"}


def _find_or_create_group(
    db: Session,
    group_data: Dict[str, Any],
    organization_id: int,
    created_by: int,
) -> ChatChannel:
    """Return existing group by name or create a new one. Caller must flush."""
    existing = (
        db.query(ChatChannel)
        .filter(
            ChatChannel.organization_id == organization_id,
            ChatChannel.parent_id.is_(None),
            ChatChannel.is_archived.is_(False),
            ChatChannel.name == group_data["name"],
        )
        .first()
    )
    if existing:
        return existing
    group = ChatChannel(
        name=group_data["name"],
        description=group_data["description"],
        avatar=group_data["avatar"],
        organization_id=organization_id,
        created_by=created_by,
    )
    db.add(group)
    db.flush()
    return group


def _seed_one_default_group(
    db: Session,
    group_data: Dict[str, Any],
    organization_id: int,
    created_by: int,
    group_idx: int,
    base_time: datetime,
) -> Dict[str, Any]:
    """Create or reuse one top-level group and its lesson-study children."""
    group = _find_or_create_group(
        db,
        group_data,
        organization_id,
        created_by,
    )
    if not (
        db.query(ChannelMember)
        .filter(
            ChannelMember.channel_id == group.id,
            ChannelMember.user_id == created_by,
        )
        .first()
    ):
        db.add(
            ChannelMember(
                channel_id=group.id,
                user_id=created_by,
                role="owner",
            )
        )

    group_base_time = base_time + timedelta(hours=group_idx * 6)
    children_summaries: List[Dict[str, Any]] = []
    children_list = group_data.get("children", [])

    for child_idx, child_data in enumerate(children_list):
        existing_child = (
            db.query(ChatChannel)
            .filter(
                ChatChannel.parent_id == group.id,
                ChatChannel.name == child_data["name"],
                ChatChannel.is_archived.is_(False),
            )
            .first()
        )
        if existing_child:
            children_summaries.append(
                {
                    "id": existing_child.id,
                    "name": existing_child.name,
                    "topic_count": 0,
                    "skipped": True,
                }
            )
            continue
        child_base = group_base_time + timedelta(hours=child_idx * 2)
        summary = _seed_lesson_study_channel(
            db,
            group.id,
            organization_id,
            created_by,
            child_data,
            child_base,
        )
        children_summaries.append(summary)

    return {
        "id": group.id,
        "name": group.name,
        "children_count": len(children_summaries),
        "children": children_summaries,
    }


def seed_default_channels(
    db: Session,
    organization_id: int,
    created_by: int,
) -> List[Dict[str, Any]]:
    """Create the default channel groups with lesson-study children.

    Skips only if the organization already has lesson-study (child) channels,
    so that groups created without children (e.g. from a partial seed) can be
    topped up. Reuses existing groups by name when adding missing children.
    """
    existing_children_count = (
        db.query(ChatChannel)
        .filter(
            ChatChannel.organization_id == organization_id,
            ChatChannel.parent_id.isnot(None),
            ChatChannel.is_archived.is_(False),
        )
        .count()
    )
    if existing_children_count > 0:
        logger.info(
            "[WorkshopChat] Org %d already has %d lesson-study channels — skipping seed",
            organization_id,
            existing_children_count,
        )
        return []

    base_time = datetime.utcnow() - timedelta(days=1)
    created_groups = [
        _seed_one_default_group(
            db,
            group_data,
            organization_id,
            created_by,
            group_idx,
            base_time,
        )
        for group_idx, group_data in enumerate(DEFAULT_CHANNEL_GROUPS)
    ]

    db.commit()

    logger.info(
        "[WorkshopChat] Seeded %d channel groups for org %d by user %d",
        len(created_groups),
        organization_id,
        created_by,
    )
    return created_groups
