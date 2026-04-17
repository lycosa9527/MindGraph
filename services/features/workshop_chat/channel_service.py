"""
Channel Service
=================

Channel CRUD and membership operations with parent-child hierarchy.

Groups (parent_id IS NULL) aggregate lesson-study channels
(parent_id IS NOT NULL).  The ``list_channels`` response nests child
channels under their parent groups.

Unread semantics (aligned with ``TopicService.list_topics`` and DM APIs):

- **Channel list badge:** non-deleted ``ChatMessage`` rows in the channel
  with ``id > ChannelMember.last_read_message_id`` (per member).
- **Topic row without** ``UserTopicPreference``: same waterline
  (``id > last_read_message_id``).
- **Topic row with preference:** non-deleted messages with
  ``created_at > UserTopicPreference.last_updated``.
- **DM:** incoming rows with ``is_read`` false.

Muted topics (``UserTopicPreference.visibility_policy == 'muted'``) are
excluded from the channel-level unread aggregate.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.functions import count as sql_count

from models.domain.auth import User
from models.domain.workshop_chat import (
    ChatChannel,
    ChannelMember,
    ChatMessage,
    ChatTopic,
    UserTopicPreference,
)
from utils.auth import is_admin

logger = logging.getLogger(__name__)


class ChannelService:
    """Channel CRUD and membership operations."""

    @staticmethod
    async def list_channels(
        db: AsyncSession,
        organization_id: int,
        user_id: Optional[int] = None,
        current_user: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Return channels grouped by parent.

        Top-level groups contain a ``children`` list of lesson-study channels.
        Announce channels are returned as standalone items (no parent).
        """
        result = await db.execute(
            select(ChatChannel)
            .where(
                ChatChannel.is_archived.is_(False),
                or_(
                    ChatChannel.organization_id == organization_id,
                    ChatChannel.channel_type == "announce",
                ),
            )
            .order_by(
                case(
                    (ChatChannel.channel_type == "announce", 0),
                    (ChatChannel.channel_type == "public", 1),
                    else_=2,
                ),
                case(
                    (ChatChannel.parent_id.is_(None), 0),
                    else_=1,
                ),
                ChatChannel.display_order.asc(),
                ChatChannel.name,
            )
        )
        channels = result.scalars().all()

        member_map = await ChannelService._build_member_map(db, user_id, channels)
        user_is_admin = is_admin(current_user) if current_user else False
        member_counts, topic_counts, unread_counts = await ChannelService._batch_channel_list_metrics(
            db,
            [c.id for c in channels],
            member_map,
        )

        groups: Dict[int, Dict[str, Any]] = {}
        standalone: List[Dict[str, Any]] = []

        for ch in channels:
            formatted = ChannelService._format_channel(
                ch,
                member_map,
                user_is_admin,
                member_count=member_counts.get(ch.id, 0),
                topic_count=topic_counts.get(ch.id, 0),
                unread_count=unread_counts.get(ch.id, 0),
            )
            if ch.parent_id is None:
                formatted["children"] = []
                groups[ch.id] = formatted
                standalone.append(formatted)
            else:
                parent = groups.get(ch.parent_id)
                if parent is not None:
                    parent["children"].append(formatted)
                else:
                    standalone.append(formatted)

        return standalone

    @staticmethod
    async def _build_member_map(
        db: AsyncSession,
        user_id: Optional[int],
        channels: List[ChatChannel],
    ) -> Dict[int, ChannelMember]:
        """Build mapping of channel_id -> ChannelMember for the given user."""
        if not user_id:
            return {}
        result = await db.execute(
            select(ChannelMember).where(
                ChannelMember.user_id == user_id,
                ChannelMember.channel_id.in_([c.id for c in channels]),
            )
        )
        memberships = result.scalars().all()
        return {m.channel_id: m for m in memberships}

    @staticmethod
    async def _batch_channel_list_metrics(
        db: AsyncSession,
        channel_ids: List[int],
        member_map: Dict[int, ChannelMember],
    ) -> Tuple[Dict[int, int], Dict[int, int], Dict[int, int]]:
        """Member counts, topic counts, and per-user unreads for list_channels."""
        if not channel_ids:
            return {}, {}, {}

        mc_result = await db.execute(
            select(
                ChannelMember.channel_id,
                sql_count(ChannelMember.user_id),
            )
            .where(ChannelMember.channel_id.in_(channel_ids))
            .group_by(ChannelMember.channel_id)
        )
        member_counts = {int(a): int(b) for a, b in mc_result.all()}

        tc_result = await db.execute(
            select(
                ChatTopic.channel_id,
                sql_count(ChatTopic.id),
            )
            .where(ChatTopic.channel_id.in_(channel_ids))
            .group_by(ChatTopic.channel_id)
        )
        topic_counts = {int(a): int(b) for a, b in tc_result.all()}

        unread_counts: Dict[int, int] = {cid: 0 for cid in channel_ids}
        if not member_map:
            return member_counts, topic_counts, unread_counts

        mids = [cid for cid in member_map if cid in channel_ids]
        or_clauses = [
            and_(
                ChatMessage.channel_id == cid,
                ChatMessage.id > (member_map[cid].last_read_message_id or 0),
            )
            for cid in mids
        ]
        uid = member_map[mids[0]].user_id if mids else None
        muted_topic_ids: tuple = ()
        if uid is not None:
            muted_result = await db.execute(
                select(UserTopicPreference.topic_id).where(
                    UserTopicPreference.user_id == uid,
                    UserTopicPreference.visibility_policy == "muted",
                )
            )
            muted_topic_ids = tuple(int(row[0]) for row in muted_result.all())
        if or_clauses:
            unread_stmt = select(
                ChatMessage.channel_id,
                sql_count(ChatMessage.id),
            ).where(
                ChatMessage.channel_id.in_(mids),
                ChatMessage.is_deleted.is_(False),
                or_(*or_clauses),
            )
            if muted_topic_ids:
                unread_stmt = unread_stmt.where(
                    or_(
                        ChatMessage.topic_id.is_(None),
                        ChatMessage.topic_id.notin_(muted_topic_ids),
                    )
                )
            unread_stmt = unread_stmt.group_by(ChatMessage.channel_id)
            unread_result = await db.execute(unread_stmt)
            for row_cid, cnt in unread_result.all():
                unread_counts[int(row_cid)] = int(cnt)

        return member_counts, topic_counts, unread_counts

    @staticmethod
    def _format_channel(
        channel: ChatChannel,
        member_map: Dict[int, ChannelMember],
        user_is_admin: bool = False,
        *,
        member_count: int,
        topic_count: int,
        unread_count: int,
    ) -> Dict[str, Any]:
        """Format a single channel with counts and membership info."""
        membership = member_map.get(channel.id)

        can_post = True
        if channel.channel_type == "announce":
            can_post = user_is_admin

        data: Dict[str, Any] = {
            "id": channel.id,
            "name": channel.name,
            "description": channel.description,
            "avatar": channel.avatar,
            "created_by": channel.created_by,
            "channel_type": channel.channel_type,
            "is_default": channel.is_default,
            "posting_policy": channel.posting_policy,
            "can_post": can_post,
            "member_count": member_count,
            "topic_count": topic_count,
            "is_joined": channel.id in member_map,
            "is_muted": membership.is_muted if membership else False,
            "pin_to_top": membership.pin_to_top if membership else False,
            "color": membership.color if membership else (channel.color or "#c2c2c2"),
            "desktop_notifications": (membership.desktop_notifications if membership else True),
            "email_notifications": (membership.email_notifications if membership else False),
            "unread_count": unread_count,
            "created_at": channel.created_at.isoformat(),
            "parent_id": channel.parent_id,
            "display_order": channel.display_order,
        }

        if channel.parent_id is not None:
            data.update(
                {
                    "status": channel.status,
                    "deadline": (channel.deadline.isoformat() if channel.deadline else None),
                    "diagram_id": channel.diagram_id,
                    "is_resolved": channel.is_resolved,
                }
            )

        return data

    @staticmethod
    async def mark_channel_read(
        db: AsyncSession,
        channel_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """Advance the member waterline to the latest non-deleted message."""
        result = await db.execute(
            select(ChannelMember).where(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            return {"marked": False}
        max_result = await db.execute(
            select(func.max(ChatMessage.id)).where(
                ChatMessage.channel_id == channel_id,
                ChatMessage.is_deleted.is_(False),
            )
        )
        max_msg_id = max_result.scalar()
        if max_msg_id:
            current = member.last_read_message_id or 0
            if max_msg_id > current:
                member.last_read_message_id = max_msg_id
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        return {
            "marked": True,
            "last_read_message_id": member.last_read_message_id,
        }

    @staticmethod
    async def create_channel(
        db: AsyncSession,
        name: str,
        organization_id: int,
        created_by: int,
        description: Optional[str] = None,
        avatar: Optional[str] = None,
        parent_id: Optional[int] = None,
        color: Optional[str] = None,
        channel_status: Optional[str] = None,
        deadline: Optional[datetime] = None,
        diagram_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a channel (group or lesson-study) and add creator as owner."""
        display_order = 0
        if parent_id is None:
            max_result = await db.execute(
                select(
                    func.coalesce(func.max(ChatChannel.display_order), -1),
                ).where(
                    ChatChannel.organization_id == organization_id,
                    ChatChannel.is_archived.is_(False),
                    ChatChannel.parent_id.is_(None),
                )
            )
            max_order = max_result.scalar()
            display_order = int(max_order) + 1

        channel = ChatChannel(
            name=name,
            description=description,
            organization_id=organization_id,
            created_by=created_by,
            avatar=avatar,
            parent_id=parent_id,
            color=color,
            status=channel_status,
            deadline=deadline,
            diagram_id=diagram_id,
            display_order=display_order,
        )
        db.add(channel)
        await db.flush()

        owner_member = ChannelMember(
            channel_id=channel.id,
            user_id=created_by,
            role="owner",
        )
        db.add(owner_member)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        logger.info(
            "[WorkshopChat] Channel '%s' (parent=%s) created by user %d in org %d",
            name,
            parent_id,
            created_by,
            organization_id,
        )
        return {
            "id": channel.id,
            "name": channel.name,
            "description": channel.description,
            "avatar": channel.avatar,
            "created_by": channel.created_by,
            "parent_id": channel.parent_id,
            "color": channel.color,
            "status": channel.status,
            "created_at": channel.created_at.isoformat(),
        }

    @staticmethod
    async def update_channel(
        db: AsyncSession,
        channel_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        avatar: Optional[str] = None,
        color: Optional[str] = None,
        channel_status: Optional[str] = None,
        deadline: Optional[datetime] = None,
        clear_deadline: bool = False,
        diagram_id: Optional[str] = None,
        is_resolved: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update channel fields (including lesson-study metadata)."""
        result = await db.execute(select(ChatChannel).where(ChatChannel.id == channel_id))
        channel = result.scalar_one_or_none()
        if not channel:
            return None
        if name is not None:
            channel.name = name
        if description is not None:
            channel.description = description
        if avatar is not None:
            channel.avatar = avatar
        if color is not None:
            channel.color = color
        if channel_status is not None:
            channel.status = channel_status
        if clear_deadline:
            channel.deadline = None
        elif deadline is not None:
            channel.deadline = deadline
        if diagram_id is not None:
            channel.diagram_id = diagram_id if diagram_id else None
        if is_resolved is not None:
            channel.is_resolved = is_resolved
        channel.updated_at = datetime.now(UTC)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        return {
            "id": channel.id,
            "name": channel.name,
            "description": channel.description,
            "avatar": channel.avatar,
            "color": channel.color,
            "status": channel.status,
            "diagram_id": channel.diagram_id,
            "is_resolved": channel.is_resolved,
            "deadline": (channel.deadline.isoformat() if channel.deadline else None),
        }

    @staticmethod
    async def archive_channel(
        db: AsyncSession,
        channel_id: int,
    ) -> bool:
        """Soft-archive a channel."""
        result = await db.execute(select(ChatChannel).where(ChatChannel.id == channel_id))
        channel = result.scalar_one_or_none()
        if not channel:
            return False
        channel.is_archived = True
        channel.updated_at = datetime.now(UTC)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        logger.info("[WorkshopChat] Channel %d archived", channel_id)
        return True

    @staticmethod
    async def join_channel(
        db: AsyncSession,
        channel_id: int,
        user_id: int,
    ) -> bool:
        """Join a channel as a member."""
        result = await db.execute(
            select(ChannelMember).where(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return True
        db.add(
            ChannelMember(
                channel_id=channel_id,
                user_id=user_id,
                role="member",
            )
        )
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        logger.info(
            "[WorkshopChat] User %d joined channel %d",
            user_id,
            channel_id,
        )
        return True

    @staticmethod
    async def leave_channel(
        db: AsyncSession,
        channel_id: int,
        user_id: int,
    ) -> bool:
        """Leave a channel."""
        result = await db.execute(
            select(ChannelMember).where(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            return False
        await db.delete(member)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        logger.info(
            "[WorkshopChat] User %d left channel %d",
            user_id,
            channel_id,
        )
        return True

    @staticmethod
    async def get_channel_members(
        db: AsyncSession,
        channel_id: int,
    ) -> List[Dict[str, Any]]:
        """List members with user details, owners first."""
        result = await db.execute(
            select(ChannelMember)
            .options(joinedload(ChannelMember.user))
            .where(ChannelMember.channel_id == channel_id)
            .order_by(
                case((ChannelMember.role == "owner", 0), else_=1),
                ChannelMember.joined_at,
            )
        )
        members = result.unique().scalars().all()
        return [
            {
                "user_id": m.user_id,
                "name": m.user.name if m.user else f"User {m.user_id}",
                "avatar": m.user.avatar if m.user else None,
                "role": m.role,
                "joined_at": m.joined_at.isoformat(),
            }
            for m in members
        ]

    @staticmethod
    async def is_channel_member(
        db: AsyncSession,
        channel_id: int,
        user_id: int,
    ) -> bool:
        """Check if user is a member of a channel."""
        result = await db.execute(
            select(ChannelMember).where(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def get_user_member_channel_ids(
        db: AsyncSession,
        user_id: int,
        channel_ids: List[int],
    ) -> set:
        """Return the subset of ``channel_ids`` where ``user_id`` is a member.

        Single SQL query instead of one per channel.
        """
        if not channel_ids:
            return set()
        result = await db.execute(
            select(ChannelMember.channel_id).where(
                ChannelMember.user_id == user_id,
                ChannelMember.channel_id.in_(channel_ids),
            )
        )
        return {row[0] for row in result.all()}

    @staticmethod
    async def get_channel(
        db: AsyncSession,
        channel_id: int,
    ) -> Optional[ChatChannel]:
        """Get a non-archived channel by ID."""
        result = await db.execute(
            select(ChatChannel).where(
                ChatChannel.id == channel_id,
                ChatChannel.is_archived.is_(False),
            )
        )
        return result.scalar_one_or_none()

    # ── Subscription preference helpers ──────────────────────────

    @staticmethod
    async def _get_membership(
        db: AsyncSession,
        channel_id: int,
        user_id: int,
    ) -> ChannelMember:
        result = await db.execute(
            select(ChannelMember).where(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            raise ValueError("Not a channel member")
        return member

    @staticmethod
    async def toggle_mute(
        db: AsyncSession,
        channel_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """Toggle mute state for a user's channel subscription."""
        member = await ChannelService._get_membership(db, channel_id, user_id)
        member.is_muted = not member.is_muted
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        return {"channel_id": channel_id, "is_muted": member.is_muted}

    @staticmethod
    async def toggle_pin(
        db: AsyncSession,
        channel_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """Toggle pin-to-top state for a user's channel subscription."""
        member = await ChannelService._get_membership(db, channel_id, user_id)
        member.pin_to_top = not member.pin_to_top
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        return {"channel_id": channel_id, "pin_to_top": member.pin_to_top}

    @staticmethod
    async def update_member_prefs(
        db: AsyncSession,
        channel_id: int,
        user_id: int,
        color: Optional[str] = None,
        desktop_notifications: Optional[bool] = None,
        email_notifications: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update per-user subscription preferences."""
        member = await ChannelService._get_membership(db, channel_id, user_id)
        if color is not None:
            member.color = color
        if desktop_notifications is not None:
            member.desktop_notifications = desktop_notifications
        if email_notifications is not None:
            member.email_notifications = email_notifications
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        return {
            "channel_id": channel_id,
            "color": member.color,
            "desktop_notifications": member.desktop_notifications,
            "email_notifications": member.email_notifications,
        }

    @staticmethod
    async def update_channel_permissions(
        db: AsyncSession,
        channel_id: int,
        channel_type: Optional[str] = None,
        posting_policy: Optional[str] = None,
        is_default: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update channel-level permission settings (manager/admin only)."""
        result = await db.execute(select(ChatChannel).where(ChatChannel.id == channel_id))
        channel = result.scalar_one_or_none()
        if not channel:
            return None

        valid_types = {"announce", "public", "private"}
        valid_policies = {"everyone", "managers", "members_only"}

        if channel_type is not None and channel_type in valid_types:
            if channel_type == "announce":
                channel.organization_id = None
            channel.channel_type = channel_type
        if posting_policy is not None and posting_policy in valid_policies:
            channel.posting_policy = posting_policy
        if is_default is not None:
            channel.is_default = is_default

        channel.updated_at = datetime.now(UTC)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        return {
            "id": channel.id,
            "channel_type": channel.channel_type,
            "posting_policy": channel.posting_policy,
            "is_default": channel.is_default,
        }

    @staticmethod
    async def reorder_teaching_groups(
        db: AsyncSession,
        organization_id: int,
        ordered_ids: List[int],
    ) -> bool:
        """Set display_order for all top-level org teaching groups."""
        result = await db.execute(
            select(ChatChannel.id).where(
                ChatChannel.organization_id == organization_id,
                ChatChannel.is_archived.is_(False),
                ChatChannel.parent_id.is_(None),
                ChatChannel.channel_type != "announce",
            )
        )
        rows = result.all()
        expected = {int(r[0]) for r in rows}
        got = list(ordered_ids)
        if set(got) != expected or len(got) != len(expected):
            return False
        # Bulk-load all channels in one query instead of one SELECT per item.
        bulk_result = await db.execute(select(ChatChannel).where(ChatChannel.id.in_(got)))
        cid_to_channel = {ch.id: ch for ch in bulk_result.scalars().all()}
        for idx, cid in enumerate(got):
            channel = cid_to_channel.get(cid)
            if not channel:
                return False
            channel.display_order = idx
            channel.updated_at = datetime.now(UTC)
        await db.commit()
        return True

    @staticmethod
    async def invite_user_to_channel(
        db: AsyncSession,
        channel_id: int,
        target_user_id: int,
        organization_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Add an org member to a channel. Announce channels not supported."""
        result = await db.execute(
            select(ChatChannel).where(
                ChatChannel.id == channel_id,
                ChatChannel.is_archived.is_(False),
            )
        )
        channel = result.scalar_one_or_none()
        if not channel:
            return None
        if channel.channel_type == "announce":
            return None
        if channel.organization_id != organization_id:
            return None
        user_result = await db.execute(select(User).where(User.id == target_user_id))
        target = user_result.scalar_one_or_none()
        if not target or target.organization_id != organization_id:
            return None
        await ChannelService.join_channel(db, channel_id, target_user_id)
        return {
            "channel_id": channel_id,
            "user_id": target_user_id,
            "channel_name": channel.name,
        }

    @staticmethod
    async def duplicate_teaching_group(
        db: AsyncSession,
        source_channel_id: int,
        created_by: int,
        organization_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Clone a top-level teaching group; does not copy children."""
        result = await db.execute(
            select(ChatChannel).where(
                ChatChannel.id == source_channel_id,
                ChatChannel.is_archived.is_(False),
                ChatChannel.organization_id == organization_id,
                ChatChannel.parent_id.is_(None),
            )
        )
        src = result.scalar_one_or_none()
        if not src or src.channel_type == "announce":
            return None
        max_result = await db.execute(
            select(
                func.coalesce(func.max(ChatChannel.display_order), -1),
            ).where(
                ChatChannel.organization_id == organization_id,
                ChatChannel.is_archived.is_(False),
                ChatChannel.parent_id.is_(None),
            )
        )
        max_order = max_result.scalar()
        suffix = " (copy)"
        base = src.name
        if len(base) + len(suffix) > 100:
            base = base[: max(0, 100 - len(suffix))]
        new_name = f"{base}{suffix}"
        channel = ChatChannel(
            name=new_name,
            description=src.description,
            organization_id=organization_id,
            created_by=created_by,
            avatar=src.avatar,
            parent_id=None,
            color=src.color,
            channel_type=src.channel_type,
            is_default=False,
            posting_policy=src.posting_policy,
            display_order=int(max_order) + 1,
        )
        db.add(channel)
        await db.flush()

        owner_member = ChannelMember(
            channel_id=channel.id,
            user_id=created_by,
            role="owner",
        )
        db.add(owner_member)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        logger.info(
            "[WorkshopChat] Channel %d duplicated as %d by user %d",
            source_channel_id,
            channel.id,
            created_by,
        )
        return {
            "id": channel.id,
            "name": channel.name,
            "description": channel.description,
            "avatar": channel.avatar,
            "created_by": channel.created_by,
            "parent_id": channel.parent_id,
            "color": channel.color,
            "status": channel.status,
            "created_at": channel.created_at.isoformat(),
        }


channel_service = ChannelService()
