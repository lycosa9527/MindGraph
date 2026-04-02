"""
Cheap fingerprints and weak ETags for workshop chat list endpoints.

Used for conditional GET (If-None-Match / 304) to skip full list serialization
when nothing relevant changed for the requesting user.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count as sql_count

from models.domain.workshop_chat import (
    ChannelMember,
    ChatChannel,
    ChatMessage,
    ChatTopic,
    UserTopicPreference,
)
from utils.auth import is_admin


def normalize_etag_value(value: str) -> str:
    """Strip weak prefix and outer quotes for comparison."""
    text = value.strip()
    weak_prefix = "W/"
    if text.upper().startswith(weak_prefix):
        text = text[2:].lstrip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1]
    return text


def etag_is_not_modified(
    if_none_match: Optional[str],
    current_etag: str,
) -> bool:
    """True if If-None-Match matches current ETag (weak comparison)."""
    if not if_none_match or not current_etag:
        return False
    want = normalize_etag_value(current_etag)
    for part in if_none_match.split(","):
        candidate = normalize_etag_value(part)
        if candidate in ("*", want):
            return True
    return False


def _weak_etag_from_payload(payload: str) -> str:
    digest = hashlib.sha256(payload.encode()).hexdigest()[:32]
    return f'W/"{digest}"'


async def _visible_channel_ids(db: AsyncSession, organization_id: int) -> List[int]:
    result = await db.execute(
        select(ChatChannel.id).where(
            ChatChannel.is_archived.is_(False),
            or_(
                ChatChannel.organization_id == organization_id,
                ChatChannel.channel_type == "announce",
            ),
        )
    )
    return list(result.scalars().all())


async def _max_message_id_for_channels(db: AsyncSession, visible_ids: List[int]) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(ChatMessage.id), 0)).where(
            ChatMessage.channel_id.in_(visible_ids),
            ChatMessage.is_deleted.is_(False),
        )
    )
    return result.scalar()


async def _membership_digest_for_channels(
    db: AsyncSession,
    user_id: int,
    visible_ids: List[int],
) -> str:
    result = await db.execute(
        select(
            ChannelMember.channel_id,
            ChannelMember.last_read_message_id,
            ChannelMember.is_muted,
            ChannelMember.pin_to_top,
            ChannelMember.color,
        )
        .where(
            ChannelMember.user_id == user_id,
            ChannelMember.channel_id.in_(visible_ids),
        )
        .order_by(ChannelMember.channel_id)
    )
    mem_rows = result.all()
    return hashlib.sha256(
        repr(tuple(mem_rows)).encode(),
    ).hexdigest()[:24]


async def _channels_fingerprint_non_empty(
    db: AsyncSession,
    visible_ids: List[int],
    user_id: int,
    organization_id: int,
    admin_bit: int,
) -> str:
    result = await db.execute(
        select(
            func.max(ChatChannel.updated_at),
            sql_count(ChatChannel.id),
            func.max(ChatChannel.id),
        ).where(ChatChannel.id.in_(visible_ids))
    )
    ch_stats = result.one()

    result = await db.execute(
        select(
            func.coalesce(
                func.max(ChatTopic.updated_at),
                datetime(1970, 1, 1),
            ),
            sql_count(ChatTopic.id),
        ).where(ChatTopic.channel_id.in_(visible_ids))
    )
    top_stats = result.one()

    max_msg_id = await _max_message_id_for_channels(db, visible_ids)
    mem_digest = await _membership_digest_for_channels(db, user_id, visible_ids)
    payload = (
        f"{ch_stats[0]!s}|{ch_stats[1]}|{ch_stats[2]}|{max_msg_id}|"
        f"{top_stats[0]!s}|{top_stats[1]}|{mem_digest}|{admin_bit}|"
        f"{user_id}|{organization_id}"
    )
    return _weak_etag_from_payload(payload)


async def channels_list_etag(
    db: AsyncSession,
    organization_id: int,
    user_id: int,
    current_user: Any,
) -> str:
    """Fingerprint for GET /channels (per user + org scope)."""
    visible_ids = await _visible_channel_ids(db, organization_id)
    admin_bit = 1 if is_admin(current_user) else 0
    if not visible_ids:
        payload = f"ch_empty|{user_id}|{organization_id}|{admin_bit}"
        return _weak_etag_from_payload(payload)
    return await _channels_fingerprint_non_empty(
        db,
        visible_ids,
        user_id,
        organization_id,
        admin_bit,
    )


async def _topics_aggregate_row(
    db: AsyncSession,
    channel_id: int,
) -> Tuple[Any, int]:
    result = await db.execute(
        select(
            func.coalesce(
                func.max(ChatTopic.updated_at),
                datetime(1970, 1, 1),
            ),
            sql_count(ChatTopic.id),
        ).where(ChatTopic.channel_id == channel_id)
    )
    top_stats = result.one()
    return top_stats[0], top_stats[1]


async def topics_list_etag(db: AsyncSession, channel_id: int, user_id: int) -> str:
    """Fingerprint for GET /channels/{id}/topics (per user)."""
    max_topic_updated, topic_count = await _topics_aggregate_row(db, channel_id)

    result = await db.execute(
        select(func.coalesce(func.max(ChatMessage.id), 0)).where(
            ChatMessage.channel_id == channel_id,
            ChatMessage.is_deleted.is_(False),
        )
    )
    max_msg_id = result.scalar()

    result = await db.execute(
        select(
            func.coalesce(
                func.max(UserTopicPreference.last_updated),
                datetime(1970, 1, 1),
            ),
        )
        .join(ChatTopic, UserTopicPreference.topic_id == ChatTopic.id)
        .where(
            ChatTopic.channel_id == channel_id,
            UserTopicPreference.user_id == user_id,
        )
    )
    pref_max = result.scalar()

    result = await db.execute(
        select(sql_count(UserTopicPreference.id))
        .join(ChatTopic, UserTopicPreference.topic_id == ChatTopic.id)
        .where(
            ChatTopic.channel_id == channel_id,
            UserTopicPreference.user_id == user_id,
        )
    )
    pref_count = result.scalar()

    payload = f"{channel_id}|{user_id}|{max_topic_updated!s}|{topic_count}|{max_msg_id}|{pref_max!s}|{pref_count}"
    return _weak_etag_from_payload(payload)
