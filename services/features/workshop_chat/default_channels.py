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
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count as sql_count

from models.domain.workshop_chat import (
    ChannelMember,
    ChatChannel,
    ChatMessage,
    ChatTopic,
)
from services.features.workshop_chat.seed_channel_data import (
    ANNOUNCE_CHANNEL,
    DEFAULT_CHANNEL_GROUPS,
    KEEPER_GROUP_NAME,
    KEEPER_LESSON_NAME,
    RETIRED_SEED_GROUP_NAMES,
    RETIRED_SEED_LESSON_NAMES,
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
    db: AsyncSession,
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


async def _seed_lesson_study_channel(
    db: AsyncSession,
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
    await db.flush()

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
        await db.flush()

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


async def _ensure_announce_topics_and_messages(
    db: AsyncSession,
    channel: ChatChannel,
    created_by: int,
    base_time: datetime,
) -> None:
    """Add missing topics and messages to an existing announce channel."""
    result = await db.execute(select(ChatTopic).where(ChatTopic.channel_id == channel.id))
    existing_titles = {t.title for t in result.scalars().all()}
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
        await db.flush()
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


async def _backfill_empty_announce_topic_messages(
    db: AsyncSession,
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
    result = await db.execute(select(ChatTopic).where(ChatTopic.channel_id == channel.id))
    topics = result.scalars().all()
    added = False
    for topic in topics:
        data = title_to_data.get(topic.title)
        if not data:
            continue
        count_result = await db.execute(
            select(sql_count(ChatMessage.id)).where(
                ChatMessage.channel_id == channel.id,
                ChatMessage.topic_id == topic.id,
                ChatMessage.is_deleted.is_(False),
            )
        )
        msg_count = count_result.scalar()
        if (msg_count or 0) > 0:
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


async def _list_announce_channels(db: AsyncSession) -> List[ChatChannel]:
    """Return every announce channel, oldest first (including archived)."""
    result = await db.execute(
        select(ChatChannel).where(ChatChannel.channel_type == "announce").order_by(ChatChannel.id.asc())
    )
    return list(result.scalars().all())


def canonical_announce_channel(
    channels: List[ChatChannel],
) -> Optional[ChatChannel]:
    """Pick the live announce channel; fall back to the oldest row."""
    if not channels:
        return None
    live = [channel for channel in channels if not channel.is_archived]
    if live:
        return live[0]
    return channels[0]


async def _dedupe_announce_channels(
    db: AsyncSession,
    channels: List[ChatChannel],
) -> Optional[ChatChannel]:
    """Keep one announce channel; archive extra live duplicates."""
    keeper = canonical_announce_channel(channels)
    if keeper is None:
        return None
    extras = [channel for channel in channels if channel.id != keeper.id and not channel.is_archived]
    changed = False
    if extras:
        for extra in extras:
            extra.is_archived = True
        changed = True
        logger.warning(
            "[WorkshopChat] Archived %d duplicate announce channel(s); keeping id=%s",
            len(extras),
            keeper.id,
        )
    if keeper.is_archived:
        keeper.is_archived = False
        changed = True
        logger.info(
            "[WorkshopChat] Restored archived announce channel id=%s as canonical",
            keeper.id,
        )
    if changed:
        await db.flush()
    return keeper


async def _resolve_announce_channel(db: AsyncSession) -> Optional[ChatChannel]:
    """Return the single canonical announce channel, collapsing duplicates."""
    return await _dedupe_announce_channels(db, await _list_announce_channels(db))


async def _top_up_existing_announce(
    db: AsyncSession,
    existing: ChatChannel,
    created_by: int,
    base_time: datetime,
) -> None:
    """Fill missing topics, messages, and membership on an announce channel."""
    count_result = await db.execute(
        select(sql_count(ChatTopic.id)).where(
            ChatTopic.channel_id == existing.id,
        )
    )
    topic_count = count_result.scalar()
    if (topic_count or 0) < len(ANNOUNCE_CHANNEL.get("topics", [])):
        await _ensure_announce_topics_and_messages(
            db,
            existing,
            created_by,
            base_time,
        )
        await db.commit()
        logger.info(
            "[WorkshopChat] Topped up announce channel '%s' with missing topics (user %d)",
            existing.name,
            created_by,
        )
    if await _backfill_empty_announce_topic_messages(
        db,
        existing,
        created_by,
        base_time,
    ):
        await db.commit()
        logger.info(
            "[WorkshopChat] Backfilled seed messages on announce channel '%s' (user %d)",
            existing.name,
            created_by,
        )
    mem_result = await db.execute(
        select(ChannelMember).where(
            ChannelMember.channel_id == existing.id,
            ChannelMember.user_id == created_by,
        )
    )
    membership = mem_result.scalar_one_or_none()
    if not membership:
        db.add(
            ChannelMember(
                channel_id=existing.id,
                user_id=created_by,
                role="owner",
            )
        )
        await db.commit()


async def _create_announce_channel(
    db: AsyncSession,
    created_by: int,
    base_time: datetime,
) -> Optional[ChatChannel]:
    """Insert a new global announce channel. ``None`` if another worker won."""
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
    try:
        await db.flush()
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
            await db.flush()
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
        await db.commit()
    except IntegrityError:
        await db.rollback()
        logger.info("[WorkshopChat] Announce channel insert raced; reusing existing row")
        return None
    logger.info(
        "[WorkshopChat] Global announce channel '%s' seeded by user %d",
        channel.name,
        created_by,
    )
    return channel


async def seed_announce_channel(
    db: AsyncSession,
    created_by: int,
) -> Optional[Dict[str, Any]]:
    """Create or top-up the global announce channel.

    The announce channel has ``organization_id = NULL`` and is visible to
    all users.  If it already exists but has no (or incomplete) topics/messages,
    we add the missing seed content so it is never left empty.

    Concurrent workers can leave more than one announce row. This function
    keeps the oldest live channel and archives the rest.
    """
    existing = await _resolve_announce_channel(db)
    base_time = datetime.now(UTC) - timedelta(hours=2)

    if existing is None:
        created = await _create_announce_channel(db, created_by, base_time)
        if created is not None:
            return {
                "id": created.id,
                "name": created.name,
                "channel_type": "announce",
            }
        existing = await _resolve_announce_channel(db)
        if existing is None:
            logger.error("[WorkshopChat] Failed to seed or resolve announce channel")
            return None

    await _top_up_existing_announce(db, existing, created_by, base_time)
    await db.commit()
    return {"id": existing.id, "name": existing.name, "channel_type": "announce"}


async def _find_or_create_group(
    db: AsyncSession,
    group_data: Dict[str, Any],
    organization_id: int,
    created_by: int,
) -> ChatChannel:
    """Return existing group by name or create a new one. Caller must flush."""
    result = await db.execute(
        select(ChatChannel).where(
            ChatChannel.organization_id == organization_id,
            ChatChannel.parent_id.is_(None),
            ChatChannel.is_archived.is_(False),
            ChatChannel.name == group_data["name"],
        )
    )
    existing = result.scalars().first()
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
    await db.flush()
    return group


async def _seed_one_default_group(
    db: AsyncSession,
    group_data: Dict[str, Any],
    organization_id: int,
    created_by: int,
    group_idx: int,
    base_time: datetime,
) -> Dict[str, Any]:
    """Create or reuse one top-level group and its lesson-study children."""
    group = await _find_or_create_group(
        db,
        group_data,
        organization_id,
        created_by,
    )
    mem_result = await db.execute(
        select(ChannelMember).where(
            ChannelMember.channel_id == group.id,
            ChannelMember.user_id == created_by,
        )
    )
    if not mem_result.scalar_one_or_none():
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
        child_result = await db.execute(
            select(ChatChannel).where(
                ChatChannel.parent_id == group.id,
                ChatChannel.name == child_data["name"],
                ChatChannel.is_archived.is_(False),
            )
        )
        existing_child = child_result.scalars().first()
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
        summary = await _seed_lesson_study_channel(
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


def _should_archive_retired_seed(
    channel: ChatChannel,
    keeper_group_id: Optional[int],
    retired_group_ids: set[int],
) -> bool:
    """True when this row is a retired demo group or lesson."""
    if channel.id in retired_group_ids or channel.parent_id in retired_group_ids:
        return True
    if channel.name in RETIRED_SEED_LESSON_NAMES:
        return True
    if (
        keeper_group_id is not None
        and channel.parent_id is None
        and channel.name == KEEPER_GROUP_NAME
        and channel.id != keeper_group_id
    ):
        return True
    if keeper_group_id is not None and channel.parent_id == keeper_group_id and channel.name != KEEPER_LESSON_NAME:
        return True
    return False


async def archive_retired_seed_channels(
    db: AsyncSession,
    organization_id: int,
) -> int:
    """Archive canned demo groups/lessons that are no longer in the seed."""
    result = await db.execute(
        select(ChatChannel).where(
            ChatChannel.organization_id == organization_id,
            ChatChannel.is_archived.is_(False),
        )
    )
    channels = list(result.scalars().all())
    keeper_group_id: Optional[int] = None
    retired_group_ids: set[int] = set()
    for channel in channels:
        if channel.parent_id is None and channel.name == KEEPER_GROUP_NAME:
            if keeper_group_id is None or channel.id < keeper_group_id:
                keeper_group_id = channel.id
        if channel.parent_id is None and channel.name in RETIRED_SEED_GROUP_NAMES:
            retired_group_ids.add(channel.id)

    archived = 0
    for channel in channels:
        if _should_archive_retired_seed(channel, keeper_group_id, retired_group_ids):
            channel.is_archived = True
            archived += 1
    archived_ids = {channel.id for channel in channels if channel.is_archived}
    for channel in channels:
        if channel.is_archived:
            continue
        if channel.parent_id is not None and channel.parent_id in archived_ids:
            channel.is_archived = True
            archived += 1
    if archived:
        await db.commit()
        logger.info(
            "[WorkshopChat] Archived %d retired seed channel(s) for org %d",
            archived,
            organization_id,
        )
    return archived


async def archive_duplicate_named_channels(
    db: AsyncSession,
    organization_id: int,
) -> int:
    """Keep the oldest live row per (parent_id, name); archive copies.

    Seed races and DB restores left two 语文教研组 / 系统公告 forests.
    """
    result = await db.execute(
        select(ChatChannel).where(
            ChatChannel.organization_id == organization_id,
            ChatChannel.is_archived.is_(False),
            ChatChannel.channel_type != "announce",
        )
    )
    channels = list(result.scalars().all())
    buckets: dict[tuple[Optional[int], str], list[ChatChannel]] = {}
    for channel in channels:
        key = (channel.parent_id, channel.name)
        buckets.setdefault(key, []).append(channel)

    archived_ids: set[int] = set()
    for rows in buckets.values():
        if len(rows) < 2:
            continue
        rows.sort(key=lambda item: item.id)
        for extra in rows[1:]:
            extra.is_archived = True
            archived_ids.add(extra.id)

    for channel in channels:
        if channel.id in archived_ids:
            continue
        if channel.parent_id is not None and channel.parent_id in archived_ids:
            channel.is_archived = True
            archived_ids.add(channel.id)

    if archived_ids:
        await db.commit()
        logger.info(
            "[WorkshopChat] Archived %d duplicate-named channel(s) for org %d",
            len(archived_ids),
            organization_id,
        )
    return len(archived_ids)


async def _ensure_channel_member(
    db: AsyncSession,
    channel_id: int,
    user_id: int,
) -> bool:
    """Add a member row when missing. True if a row was inserted."""
    existing = await db.execute(
        select(ChannelMember.id).where(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == user_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False
    db.add(
        ChannelMember(
            channel_id=channel_id,
            user_id=user_id,
            role="member",
        )
    )
    return True


async def ensure_default_stream_memberships(
    db: AsyncSession,
    organization_id: int,
    user_id: int,
) -> int:
    """Subscribe the user to keeper 教研组 + 课例 (Zulip default streams)."""
    result = await db.execute(
        select(ChatChannel).where(
            ChatChannel.organization_id == organization_id,
            ChatChannel.is_archived.is_(False),
        )
    )
    channels = list(result.scalars().all())
    keeper_group_id: Optional[int] = None
    for channel in channels:
        if channel.parent_id is None and channel.name == KEEPER_GROUP_NAME:
            keeper_group_id = channel.id
            break
    if keeper_group_id is None:
        return 0

    target_ids = [keeper_group_id]
    for channel in channels:
        if channel.parent_id == keeper_group_id and channel.name == KEEPER_LESSON_NAME:
            target_ids.append(channel.id)

    added = 0
    for channel_id in target_ids:
        if await _ensure_channel_member(db, channel_id, user_id):
            added += 1
    if added:
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            return 0
        logger.info(
            "[WorkshopChat] Default-stream memberships +%d for user %d org %d",
            added,
            user_id,
            organization_id,
        )
    return added


async def seed_default_channels(
    db: AsyncSession,
    organization_id: int,
    created_by: int,
) -> List[Dict[str, Any]]:
    """Create the default channel groups with lesson-study children.

    Archives retired demo names first. Skips create if the organization
    already has lesson-study (child) channels, so that groups created
    without children (e.g. from a partial seed) can be topped up.
    """
    await archive_retired_seed_channels(db, organization_id)
    await archive_duplicate_named_channels(db, organization_id)
    count_result = await db.execute(
        select(sql_count(ChatChannel.id)).where(
            ChatChannel.organization_id == organization_id,
            ChatChannel.parent_id.isnot(None),
            ChatChannel.is_archived.is_(False),
        )
    )
    existing_children_count = count_result.scalar()
    if (existing_children_count or 0) > 0:
        logger.info(
            "[WorkshopChat] Org %d already has %d lesson-study channels — skipping seed",
            organization_id,
            existing_children_count,
        )
        await ensure_default_stream_memberships(db, organization_id, created_by)
        return []

    base_time = datetime.now(UTC) - timedelta(days=1)
    created_groups = []
    for group_idx, group_data in enumerate(DEFAULT_CHANNEL_GROUPS):
        group_result = await _seed_one_default_group(
            db,
            group_data,
            organization_id,
            created_by,
            group_idx,
            base_time,
        )
        created_groups.append(group_result)

    await db.commit()
    await ensure_default_stream_memberships(db, organization_id, created_by)

    logger.info(
        "[WorkshopChat] Seeded %d channel groups for org %d by user %d",
        len(created_groups),
        organization_id,
        created_by,
    )
    return created_groups
