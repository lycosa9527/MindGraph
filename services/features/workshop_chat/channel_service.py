"""
Channel Service
=================

Channel CRUD and membership operations with parent-child hierarchy.

Groups (parent_id IS NULL) aggregate lesson-study channels
(parent_id IS NOT NULL).  The ``list_channels`` response nests child
channels under their parent groups.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import case, or_
from sqlalchemy.orm import Session, joinedload

from models.domain.workshop_chat import (
    ChatChannel, ChannelMember, ChatTopic, ChatMessage,
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
                ChatChannel.name,
            )
            .all()
        )

        member_map = ChannelService._build_member_map(db, user_id, channels)
        user_is_admin = is_admin(current_user) if current_user else False

        groups: Dict[int, Dict[str, Any]] = {}
        standalone: List[Dict[str, Any]] = []

        for ch in channels:
            formatted = ChannelService._format_channel(
                db, ch, member_map, user_is_admin,
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
    def _format_channel(
        db: Session,
        channel: ChatChannel,
        member_map: Dict[int, ChannelMember],
        user_is_admin: bool = False,
    ) -> Dict[str, Any]:
        """Format a single channel with counts and membership info."""
        member_count = (
            db.query(ChannelMember)
            .filter(ChannelMember.channel_id == channel.id)
            .count()
        )
        topic_count = (
            db.query(ChatTopic)
            .filter(ChatTopic.channel_id == channel.id)
            .count()
        )

        membership = member_map.get(channel.id)
        unread_count = 0
        if membership:
            last_read = membership.last_read_message_id or 0
            unread_count = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.channel_id == channel.id,
                    ChatMessage.id > last_read,
                    ChatMessage.is_deleted.is_(False),
                )
                .count()
            )

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
            "unread_count": unread_count,
            "created_at": channel.created_at.isoformat(),
            "parent_id": channel.parent_id,
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
        if deadline is not None:
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


channel_service = ChannelService()
