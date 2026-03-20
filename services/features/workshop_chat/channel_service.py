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
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session, joinedload
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
    def list_channels(
        db: Session,
        organization_id: int,
        user_id: Optional[int] = None,
        current_user: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Return channels grouped by parent.

        Top-level groups contain a ``children`` list of lesson-study channels.
        Announce channels are returned as standalone items (no parent).
        """
        # Order so parents (parent_id IS NULL) always come before their children.
        # Otherwise children can appear before the parent in the list and get appended
        # to standalone instead of parent["children"], leaving groups with empty children.
        channels = (
            db.query(ChatChannel)
            .filter(
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
                # Parents first (parent_id IS NULL -> 0), then children (1), then by name
                case(
                    (ChatChannel.parent_id.is_(None), 0),
                    else_=1,
                ),
                ChatChannel.display_order.asc(),
                ChatChannel.name,
            )
            .all()
        )

        member_map = ChannelService._build_member_map(db, user_id, channels)
        user_is_admin = is_admin(current_user) if current_user else False
        member_counts, topic_counts, unread_counts = (
            ChannelService._batch_channel_list_metrics(
                db, [c.id for c in channels], member_map,
            )
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
    def _build_member_map(
        db: Session,
        user_id: Optional[int],
        channels: List[ChatChannel],
    ) -> Dict[int, ChannelMember]:
        """Build mapping of channel_id -> ChannelMember for the given user."""
        if not user_id:
            return {}
        memberships = (
            db.query(ChannelMember)
            .filter(
                ChannelMember.user_id == user_id,
                ChannelMember.channel_id.in_([c.id for c in channels]),
            )
            .all()
        )
        return {m.channel_id: m for m in memberships}

    @staticmethod
    def _batch_channel_list_metrics(
        db: Session,
        channel_ids: List[int],
        member_map: Dict[int, ChannelMember],
    ) -> Tuple[Dict[int, int], Dict[int, int], Dict[int, int]]:
        """Member counts, topic counts, and per-user unreads for list_channels."""
        if not channel_ids:
            return {}, {}, {}
        member_counts = {
            int(a): int(b)
            for a, b in db.query(
                ChannelMember.channel_id, sql_count(ChannelMember.user_id),
            )
            .filter(ChannelMember.channel_id.in_(channel_ids))
            .group_by(ChannelMember.channel_id)
            .all()
        }
        topic_counts = {
            int(a): int(b)
            for a, b in db.query(
                ChatTopic.channel_id, sql_count(ChatTopic.id),
            )
            .filter(ChatTopic.channel_id.in_(channel_ids))
            .group_by(ChatTopic.channel_id)
            .all()
        }
        unread_counts = {cid: 0 for cid in channel_ids}
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
        muted_topic_ids = ()
        if uid is not None:
            muted_topic_ids = tuple(
                int(row[0])
                for row in db.query(UserTopicPreference.topic_id)
                .filter(
                    UserTopicPreference.user_id == uid,
                    UserTopicPreference.visibility_policy == "muted",
                )
                .all()
            )
        if or_clauses:
            q_unread = (
                db.query(ChatMessage.channel_id, sql_count(ChatMessage.id))
                .filter(
                    ChatMessage.channel_id.in_(mids),
                    ChatMessage.is_deleted.is_(False),
                    or_(*or_clauses),
                )
            )
            if muted_topic_ids:
                q_unread = q_unread.filter(
                    or_(
                        ChatMessage.topic_id.is_(None),
                        ChatMessage.topic_id.notin_(muted_topic_ids),
                    )
                )
            q_unread = q_unread.group_by(ChatMessage.channel_id)
            for row_cid, cnt in q_unread.all():
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
            "desktop_notifications": (
                membership.desktop_notifications if membership else True
            ),
            "email_notifications": (
                membership.email_notifications if membership else False
            ),
            "unread_count": unread_count,
            "created_at": channel.created_at.isoformat(),
            "parent_id": channel.parent_id,
            "display_order": channel.display_order,
        }

        if channel.parent_id is not None:
            data.update({
                "status": channel.status,
                "deadline": (
                    channel.deadline.isoformat() if channel.deadline else None
                ),
                "diagram_id": channel.diagram_id,
                "is_resolved": channel.is_resolved,
            })

        return data

    @staticmethod
    def mark_channel_read(
        db: Session, channel_id: int, user_id: int,
    ) -> Dict[str, Any]:
        """Advance the member waterline to the latest non-deleted message."""
        member = (
            db.query(ChannelMember)
            .filter(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user_id,
            )
            .first()
        )
        if not member:
            return {"marked": False}
        max_msg_id = (
            db.query(func.max(ChatMessage.id))
            .filter(
                ChatMessage.channel_id == channel_id,
                ChatMessage.is_deleted.is_(False),
            )
            .scalar()
        )
        if max_msg_id:
            current = member.last_read_message_id or 0
            if max_msg_id > current:
                member.last_read_message_id = max_msg_id
        db.commit()
        return {
            "marked": True,
            "last_read_message_id": member.last_read_message_id,
        }

    @staticmethod
    def create_channel(
        db: Session,
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
            max_order = (
                db.query(func.coalesce(func.max(ChatChannel.display_order), -1))
                .filter(
                    ChatChannel.organization_id == organization_id,
                    ChatChannel.is_archived.is_(False),
                    ChatChannel.parent_id.is_(None),
                )
                .scalar()
            )
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
        db.flush()

        owner_member = ChannelMember(
            channel_id=channel.id, user_id=created_by, role="owner",
        )
        db.add(owner_member)
        db.commit()

        logger.info(
            "[WorkshopChat] Channel '%s' (parent=%s) created by user %d in org %d",
            name, parent_id, created_by, organization_id,
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
    def update_channel(
        db: Session,
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
        channel = db.query(ChatChannel).filter(ChatChannel.id == channel_id).first()
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
        channel.updated_at = datetime.utcnow()
        db.commit()
        return {
            "id": channel.id, "name": channel.name,
            "description": channel.description, "avatar": channel.avatar,
            "color": channel.color, "status": channel.status,
            "diagram_id": channel.diagram_id, "is_resolved": channel.is_resolved,
            "deadline": (
                channel.deadline.isoformat() if channel.deadline else None
            ),
        }

    @staticmethod
    def archive_channel(db: Session, channel_id: int) -> bool:
        """Soft-archive a channel."""
        channel = db.query(ChatChannel).filter(ChatChannel.id == channel_id).first()
        if not channel:
            return False
        channel.is_archived = True
        channel.updated_at = datetime.utcnow()
        db.commit()
        logger.info("[WorkshopChat] Channel %d archived", channel_id)
        return True

    @staticmethod
    def join_channel(db: Session, channel_id: int, user_id: int) -> bool:
        """Join a channel as a member."""
        existing = (
            db.query(ChannelMember)
            .filter(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user_id,
            )
            .first()
        )
        if existing:
            return True
        db.add(ChannelMember(channel_id=channel_id, user_id=user_id, role="member"))
        db.commit()
        logger.info("[WorkshopChat] User %d joined channel %d", user_id, channel_id)
        return True

    @staticmethod
    def leave_channel(db: Session, channel_id: int, user_id: int) -> bool:
        """Leave a channel."""
        member = (
            db.query(ChannelMember)
            .filter(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user_id,
            )
            .first()
        )
        if not member:
            return False
        db.delete(member)
        db.commit()
        logger.info("[WorkshopChat] User %d left channel %d", user_id, channel_id)
        return True

    @staticmethod
    def get_channel_members(db: Session, channel_id: int) -> List[Dict[str, Any]]:
        """List members with user details, owners first."""
        members = (
            db.query(ChannelMember)
            .options(joinedload(ChannelMember.user))
            .filter(ChannelMember.channel_id == channel_id)
            .order_by(
                case((ChannelMember.role == "owner", 0), else_=1),
                ChannelMember.joined_at,
            )
            .all()
        )
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
    def is_channel_member(db: Session, channel_id: int, user_id: int) -> bool:
        """Check if user is a member of a channel."""
        return (
            db.query(ChannelMember)
            .filter(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user_id,
            )
            .first()
        ) is not None

    @staticmethod
    def get_channel(db: Session, channel_id: int) -> Optional[ChatChannel]:
        """Get a non-archived channel by ID."""
        return (
            db.query(ChatChannel)
            .filter(ChatChannel.id == channel_id, ChatChannel.is_archived.is_(False))
            .first()
        )

    # ── Subscription preference helpers ──────────────────────────

    @staticmethod
    def _get_membership(
        db: Session, channel_id: int, user_id: int,
    ) -> ChannelMember:
        member = (
            db.query(ChannelMember)
            .filter(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user_id,
            )
            .first()
        )
        if not member:
            raise ValueError("Not a channel member")
        return member

    @staticmethod
    def toggle_mute(
        db: Session, channel_id: int, user_id: int,
    ) -> Dict[str, Any]:
        """Toggle mute state for a user's channel subscription."""
        member = ChannelService._get_membership(db, channel_id, user_id)
        member.is_muted = not member.is_muted
        db.commit()
        return {"channel_id": channel_id, "is_muted": member.is_muted}

    @staticmethod
    def toggle_pin(
        db: Session, channel_id: int, user_id: int,
    ) -> Dict[str, Any]:
        """Toggle pin-to-top state for a user's channel subscription."""
        member = ChannelService._get_membership(db, channel_id, user_id)
        member.pin_to_top = not member.pin_to_top
        db.commit()
        return {"channel_id": channel_id, "pin_to_top": member.pin_to_top}

    @staticmethod
    def update_member_prefs(
        db: Session,
        channel_id: int,
        user_id: int,
        color: Optional[str] = None,
        desktop_notifications: Optional[bool] = None,
        email_notifications: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update per-user subscription preferences."""
        member = ChannelService._get_membership(db, channel_id, user_id)
        if color is not None:
            member.color = color
        if desktop_notifications is not None:
            member.desktop_notifications = desktop_notifications
        if email_notifications is not None:
            member.email_notifications = email_notifications
        db.commit()
        return {
            "channel_id": channel_id,
            "color": member.color,
            "desktop_notifications": member.desktop_notifications,
            "email_notifications": member.email_notifications,
        }

    @staticmethod
    def update_channel_permissions(
        db: Session,
        channel_id: int,
        channel_type: Optional[str] = None,
        posting_policy: Optional[str] = None,
        is_default: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update channel-level permission settings (manager/admin only)."""
        channel = (
            db.query(ChatChannel)
            .filter(ChatChannel.id == channel_id)
            .first()
        )
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

        channel.updated_at = datetime.utcnow()
        db.commit()
        return {
            "id": channel.id,
            "channel_type": channel.channel_type,
            "posting_policy": channel.posting_policy,
            "is_default": channel.is_default,
        }

    @staticmethod
    def reorder_teaching_groups(
        db: Session,
        organization_id: int,
        ordered_ids: List[int],
    ) -> bool:
        """Set display_order for all top-level org teaching groups (non-announce)."""
        rows = (
            db.query(ChatChannel.id)
            .filter(
                ChatChannel.organization_id == organization_id,
                ChatChannel.is_archived.is_(False),
                ChatChannel.parent_id.is_(None),
                ChatChannel.channel_type != "announce",
            )
            .all()
        )
        expected = {int(r[0]) for r in rows}
        got = list(ordered_ids)
        if set(got) != expected or len(got) != len(expected):
            return False
        for idx, cid in enumerate(got):
            channel = (
                db.query(ChatChannel)
                .filter(ChatChannel.id == cid)
                .first()
            )
            if not channel:
                return False
            channel.display_order = idx
            channel.updated_at = datetime.utcnow()
        db.commit()
        return True

    @staticmethod
    def invite_user_to_channel(
        db: Session,
        channel_id: int,
        target_user_id: int,
        organization_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Add an org member to a channel. Announce channels are not supported."""
        channel = (
            db.query(ChatChannel)
            .filter(
                ChatChannel.id == channel_id,
                ChatChannel.is_archived.is_(False),
            )
            .first()
        )
        if not channel:
            return None
        if channel.channel_type == "announce":
            return None
        if channel.organization_id != organization_id:
            return None
        target = db.query(User).filter(User.id == target_user_id).first()
        if not target or target.organization_id != organization_id:
            return None
        ChannelService.join_channel(db, channel_id, target_user_id)
        return {
            "channel_id": channel_id,
            "user_id": target_user_id,
            "channel_name": channel.name,
        }

    @staticmethod
    def duplicate_teaching_group(
        db: Session,
        source_channel_id: int,
        created_by: int,
        organization_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Clone a top-level teaching group; does not copy lesson-study children."""
        src = (
            db.query(ChatChannel)
            .filter(
                ChatChannel.id == source_channel_id,
                ChatChannel.is_archived.is_(False),
                ChatChannel.organization_id == organization_id,
                ChatChannel.parent_id.is_(None),
            )
            .first()
        )
        if not src or src.channel_type == "announce":
            return None
        max_order = (
            db.query(func.coalesce(func.max(ChatChannel.display_order), -1))
            .filter(
                ChatChannel.organization_id == organization_id,
                ChatChannel.is_archived.is_(False),
                ChatChannel.parent_id.is_(None),
            )
            .scalar()
        )
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
        db.flush()

        owner_member = ChannelMember(
            channel_id=channel.id, user_id=created_by, role="owner",
        )
        db.add(owner_member)
        db.commit()
        logger.info(
            "[WorkshopChat] Channel %d duplicated as %d by user %d",
            source_channel_id, channel.id, created_by,
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
