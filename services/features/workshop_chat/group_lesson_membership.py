"""Cascade 教研组 membership onto 课例 children.

Joining a teaching group subscribes the user to every live lesson under it.
Creating a lesson copies current group members. Teachers who already joined
the group are backfilled on the next channel list.
"""

from __future__ import annotations

import logging
from typing import Iterable, List, Optional, Sequence, Set

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.workshop_chat import ChannelMember, ChatChannel
from services.utils.error_types import DATABASE_ERRORS

logger = logging.getLogger(__name__)


def is_teaching_group(channel: ChatChannel) -> bool:
    """True for a top-level 教研组 (not 系统公告, not a 课例)."""
    return channel.parent_id is None and channel.channel_type != "announce"


async def child_channel_ids(
    db: AsyncSession,
    group_id: int,
    *,
    live_only: bool,
) -> List[int]:
    """Return 课例 ids under ``group_id``."""
    filters = [ChatChannel.parent_id == group_id]
    if live_only:
        filters.append(ChatChannel.is_archived.is_(False))
    result = await db.execute(select(ChatChannel.id).where(*filters))
    return [int(row[0]) for row in result.all()]


async def existing_member_channel_ids(
    db: AsyncSession,
    user_id: int,
    channel_ids: Sequence[int],
) -> Set[int]:
    """Return the subset of ``channel_ids`` where ``user_id`` already has a row."""
    if not channel_ids:
        return set()
    result = await db.execute(
        select(ChannelMember.channel_id).where(
            ChannelMember.user_id == user_id,
            ChannelMember.channel_id.in_(list(channel_ids)),
        )
    )
    return {int(row[0]) for row in result.all()}


async def add_missing_memberships(
    db: AsyncSession,
    user_id: int,
    channel_ids: Sequence[int],
) -> int:
    """Insert ``member`` rows for channels the user does not already have."""
    existing = await existing_member_channel_ids(db, user_id, channel_ids)
    added = 0
    for channel_id in channel_ids:
        if channel_id in existing:
            continue
        db.add(
            ChannelMember(
                channel_id=channel_id,
                user_id=user_id,
                role="member",
            )
        )
        added += 1
    return added


async def subscribe_user_to_group_lessons(
    db: AsyncSession,
    group_id: int,
    user_id: int,
) -> int:
    """Subscribe ``user_id`` to every live 课例 under the 教研组. No commit."""
    lesson_ids = await child_channel_ids(db, group_id, live_only=True)
    return await add_missing_memberships(db, user_id, lesson_ids)


async def subscribe_group_members_to_lesson(
    db: AsyncSession,
    group_id: int,
    lesson_id: int,
    skip_user_ids: Optional[Iterable[int]] = None,
) -> int:
    """Copy current 教研组成员 onto a new 课例. No commit."""
    skip = {int(uid) for uid in (skip_user_ids or ())}
    members_result = await db.execute(select(ChannelMember.user_id).where(ChannelMember.channel_id == group_id))
    user_ids = [int(row[0]) for row in members_result.all() if int(row[0]) not in skip]
    if not user_ids:
        return 0
    present_result = await db.execute(select(ChannelMember.user_id).where(ChannelMember.channel_id == lesson_id))
    already = {int(row[0]) for row in present_result.all()}
    added = 0
    for user_id in user_ids:
        if user_id in already:
            continue
        db.add(
            ChannelMember(
                channel_id=lesson_id,
                user_id=user_id,
                role="member",
            )
        )
        added += 1
    return added


async def remove_user_from_group_lessons(
    db: AsyncSession,
    group_id: int,
    user_id: int,
) -> None:
    """Drop 课例 memberships when the user leaves the 教研组. No commit."""
    lesson_ids = await child_channel_ids(db, group_id, live_only=False)
    if not lesson_ids:
        return
    await db.execute(
        delete(ChannelMember).where(
            ChannelMember.user_id == user_id,
            ChannelMember.channel_id.in_(lesson_ids),
        )
    )


async def backfill_joined_group_lessons(
    db: AsyncSession,
    user_id: int,
    channels: Sequence[ChatChannel],
) -> int:
    """Subscribe a group member to any 课例 they are still missing. Commits."""
    group_ids = [channel.id for channel in channels if is_teaching_group(channel)]
    if not group_ids:
        return 0
    joined_groups = await existing_member_channel_ids(db, user_id, group_ids)
    added = 0
    for group_id in joined_groups:
        added += await subscribe_user_to_group_lessons(db, group_id, user_id)
    if not added:
        return 0
    try:
        await db.commit()
    except DATABASE_ERRORS:
        await db.rollback()
        raise
    logger.info(
        "[WorkshopChat] Backfilled %d lesson memberships for user %d",
        added,
        user_id,
    )
    return added


async def _load_live_channel(
    db: AsyncSession,
    channel_id: int,
) -> Optional[ChatChannel]:
    """Load a non-archived channel."""
    result = await db.execute(
        select(ChatChannel).where(
            ChatChannel.id == channel_id,
            ChatChannel.is_archived.is_(False),
        )
    )
    return result.scalar_one_or_none()


async def join_channel_with_lessons(
    db: AsyncSession,
    channel_id: int,
    user_id: int,
) -> bool:
    """Join a channel; a 教研组 join also subscribes to its 课例."""
    channel = await _load_live_channel(db, channel_id)
    if channel is None:
        return False
    added = await add_missing_memberships(db, user_id, [channel_id])
    lesson_added = 0
    if is_teaching_group(channel):
        lesson_added = await subscribe_user_to_group_lessons(db, channel_id, user_id)
    if added or lesson_added:
        try:
            await db.commit()
        except DATABASE_ERRORS:
            await db.rollback()
            raise
        logger.info(
            "[WorkshopChat] User %d joined channel %d (lessons +%d)",
            user_id,
            channel_id,
            lesson_added,
        )
    return True


async def leave_channel_with_lessons(
    db: AsyncSession,
    channel_id: int,
    user_id: int,
) -> bool:
    """Leave a channel; leaving a 教研组 also leaves its 课例."""
    result = await db.execute(
        select(ChannelMember).where(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        return False
    channel_result = await db.execute(select(ChatChannel).where(ChatChannel.id == channel_id))
    channel = channel_result.scalar_one_or_none()
    await db.delete(member)
    if channel is not None and is_teaching_group(channel):
        await remove_user_from_group_lessons(db, channel_id, user_id)
    try:
        await db.commit()
    except DATABASE_ERRORS:
        await db.rollback()
        raise
    logger.info(
        "[WorkshopChat] User %d left channel %d",
        user_id,
        channel_id,
    )
    return True


async def ensure_lesson_membership_if_group_member(
    db: AsyncSession,
    channel_id: int,
    user_id: int,
) -> bool:
    """True when the user may use this channel.

    Direct members pass. A 课例 also passes when the user is in its 教研组;
    the missing child row is inserted so unread / mute stay consistent.
    """
    direct = await existing_member_channel_ids(db, user_id, [channel_id])
    if channel_id in direct:
        return True
    channel = await _load_live_channel(db, channel_id)
    if channel is None or channel.parent_id is None:
        return False
    parent_ids = await existing_member_channel_ids(db, user_id, [channel.parent_id])
    if channel.parent_id not in parent_ids:
        return False
    added = await add_missing_memberships(db, user_id, [channel_id])
    if not added:
        return True
    try:
        await db.commit()
    except DATABASE_ERRORS:
        await db.rollback()
        recovered = await existing_member_channel_ids(db, user_id, [channel_id])
        return channel_id in recovered
    logger.info(
        "[WorkshopChat] User %d inherited lesson %d from group %d",
        user_id,
        channel_id,
        channel.parent_id,
    )
    return True
