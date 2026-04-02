"""
Workshop Chat Access Control
===============================

Reusable access-control helpers inspired by Zulip's
``zerver/lib/streams.py`` (``access_stream_by_id``, etc.) and
``zerver/decorator.py`` (``require_realm_admin``).

Every endpoint that touches a channel or DM partner calls these helpers
instead of ad-hoc HTTPException checks, ensuring consistent org isolation
across the entire module.

Channel type rules:
- ``announce``: org_id is NULL, visible to all, admin-only posting.
- ``public``: org-scoped, all org members can read/join.
- ``private``: org-scoped, membership required for read/write.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.workshop_chat import ChatChannel
from services.features.workshop_chat.channel_service import channel_service
from utils.auth import can_moderate_workshop_channel, is_admin, is_manager


def get_effective_org_id(
    current_user: User,
    requested_org_id: Optional[int] = None,
) -> int:
    """Resolve the effective organization ID.

    Admins may override to view another org's data.
    Raises 400 if the user has no organization.
    """
    if requested_org_id is not None and is_admin(current_user):
        return requested_org_id
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not part of an organization",
        )
    return current_user.organization_id


async def access_channel(
    db: AsyncSession,
    channel_id: int,
    current_user: User,
) -> ChatChannel:
    """Get a channel and verify the user has read access.

    - Announce channels: readable by everyone.
    - Public channels: user's org must match channel's org (admins bypass).
    - Private channels: same org check + membership required.
    """
    result = await db.execute(
        select(ChatChannel).where(
            ChatChannel.id == channel_id,
            ChatChannel.is_archived.is_(False),
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    if channel.channel_type == "announce":
        return channel

    if channel.organization_id != current_user.organization_id and not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your organization",
        )

    if channel.channel_type == "private":
        if not await channel_service.is_channel_member(
            db,
            channel_id,
            current_user.id,
        ) and not is_admin(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This channel is private",
            )

    return channel


def require_post_permission(
    channel: ChatChannel,
    current_user: User,
) -> None:
    """Raise 403 if the user cannot post in this channel.

    - Announce channels: admin-only.
    - Posting policy 'managers': only managers/admins can post.
    - Posting policy 'members_only': only channel members (handled by
      membership check elsewhere).
    """
    if channel.channel_type == "announce":
        if not is_admin(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can post in announcement channels",
            )
        return

    if channel.posting_policy == "managers":
        if not is_manager(current_user) and not is_admin(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only managers can post in this channel",
            )


async def require_membership(
    db: AsyncSession,
    channel_id: int,
    user_id: int,
) -> None:
    """Raise 403 if the user is not a member of the channel.

    Analogous to checking ``Subscription`` existence in Zulip.
    """
    if not await channel_service.is_channel_member(db, channel_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must join this channel first",
        )


async def require_membership_unless_announce(
    db: AsyncSession,
    channel: ChatChannel,
    user_id: int,
) -> None:
    """Require channel subscription except for global announce channels.

    Announce channels are readable (and postable per policy) without a
    ``ChannelMember`` row, matching :func:`access_channel`.
    """
    if channel.channel_type == "announce":
        return
    await require_membership(db, channel.id, user_id)


def require_channel_manager(
    current_user: User,
    channel: ChatChannel,
) -> None:
    """Raise 403 unless the user can manage this channel (Zulip-style).

    Realm admins (``is_admin``), org managers for org channels, or the user
    who created the channel may update settings. Global announce channels
    require a full admin.
    """
    if channel.channel_type == "announce":
        if not is_admin(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can manage announcement channels",
            )
        return

    if channel.organization_id != current_user.organization_id and not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    if can_moderate_workshop_channel(current_user, channel):
        return
    if channel.created_by == current_user.id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Permission denied",
    )


async def access_dm_partner(
    db: AsyncSession,
    current_user: User,
    partner_id: int,
) -> User:
    """Get a DM partner and verify same-org membership.

    Returns the partner ``User`` on success.
    """
    partner_result = await db.execute(select(User).where(User.id == partner_id))
    partner = partner_result.scalar_one_or_none()
    if not partner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if partner.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot message users outside your organization",
        )
    return partner
