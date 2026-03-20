"""
Workshop Chat Models for MindGraph
====================================

Database models for the school-scoped communication system:
- ChatChannel: Either a group/section (parent) or a lesson-study channel (child).
  Groups aggregate lesson studies; lesson-study channels contain conversations.
- ChannelMember: Membership tracking with unread state
- ChatTopic: Lightweight conversation thread within a channel (Zulip-style topic)
- ChatMessage: Messages belonging to channels (general) or topics (conversation)
- DirectMessage: 1:1 private conversations between teachers
- MessageReaction: Emoji reactions on messages
- StarredMessage: User-bookmarked messages
- FileAttachment: Files attached to messages or DMs

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Integer, String, Text, DateTime, ForeignKey, Boolean, JSON,
    Index, CheckConstraint, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base


class ChatChannel(Base):
    """
    Either a group/section or a lesson-study channel.

    Hierarchy (mirrors Zulip's Channel > Topic):
    - ``parent_id IS NULL``: top-level group (e.g. 语文教研组).
    - ``parent_id IS NOT NULL``: lesson-study channel under that group.

    Lesson-study channels carry optional ``status``, ``deadline``, and
    ``diagram_id`` for tracking study-case progress.

    Three channel types:
    - ``announce``: organization_id is NULL, visible to all users globally,
      admin-only posting. Used for system-wide announcements.
    - ``public``: org-scoped, all org members can see and join.
    - ``private``: org-scoped, invite-only within the same org.
    """
    __tablename__ = "chat_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    organization_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=True, index=True,
    )
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
    )
    avatar: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    channel_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="public",
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    posting_policy: Mapped[str] = mapped_column(
        String(20), nullable=False, default="everyone",
    )

    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("chat_channels.id"), nullable=True, index=True,
    )
    color: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    diagram_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("diagrams.id"), nullable=True, index=True,
    )
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)

    display_order: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default="0",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    organization = relationship("Organization", backref="chat_channels")
    creator = relationship("User", backref="created_channels", foreign_keys=[created_by])
    parent = relationship(
        "ChatChannel", remote_side=[id], backref="children",
        foreign_keys=[parent_id],
    )
    diagram = relationship(
        "Diagram", backref="chat_channel_diagrams", foreign_keys=[diagram_id],
    )
    members = relationship(
        "ChannelMember", back_populates="channel", cascade="all, delete-orphan",
    )
    topics = relationship(
        "ChatTopic", back_populates="channel", cascade="all, delete-orphan",
    )
    messages = relationship(
        "ChatMessage", back_populates="channel", cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "channel_type IN ('announce', 'public', 'private')",
            name="ck_chat_channels_type",
        ),
        CheckConstraint(
            "posting_policy IN ('everyone', 'managers', 'members_only')",
            name="ck_chat_channels_posting_policy",
        ),
        Index("ix_chat_channels_org_name", "organization_id", "name"),
        Index("ix_chat_channels_org_archived", "organization_id", "is_archived"),
        Index("ix_chat_channels_type", "channel_type"),
        Index("ix_chat_channels_parent", "parent_id"),
    )

    @property
    def is_group(self) -> bool:
        """True when this channel acts as a section/group header."""
        return self.parent_id is None and self.channel_type != "announce"

    @property
    def is_lesson_study(self) -> bool:
        """True when this channel represents a lesson-study (child channel)."""
        return self.parent_id is not None

    def __repr__(self) -> str:
        kind = "group" if self.is_group else "lesson-study"
        return f"<ChatChannel {self.id}: {self.name} ({kind}/{self.channel_type})>"


class ChannelMember(Base):
    """
    Tracks which users have joined which channels.

    Stores per-user read state, mute preference, and notification overrides.
    """
    __tablename__ = "channel_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_channels.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    last_read_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_muted: Mapped[bool] = mapped_column(Boolean, default=False)
    pin_to_top: Mapped[bool] = mapped_column(Boolean, default=False)
    color: Mapped[str] = mapped_column(String(10), nullable=False, default="#c2c2c2")
    desktop_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    channel = relationship("ChatChannel", back_populates="members")
    user = relationship("User", backref="channel_memberships")

    __table_args__ = (
        UniqueConstraint("channel_id", "user_id", name="uq_channel_member"),
        Index("ix_channel_members_user_channel", "user_id", "channel_id"),
    )

    def __repr__(self) -> str:
        return f"<ChannelMember channel={self.channel_id} user={self.user_id}>"


class ChatTopic(Base):
    """
    Lightweight conversation thread within a channel (Zulip-style topic).

    A topic is just a label that groups related messages.  Heavyweight
    metadata (status, deadline, diagram) now lives on ChatChannel for
    lesson-study channels.
    """
    __tablename__ = "chat_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_channels.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open",
    )
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    channel = relationship("ChatChannel", back_populates="topics")
    creator = relationship("User", backref="created_topics", foreign_keys=[created_by])
    messages = relationship(
        "ChatMessage",
        back_populates="topic",
        cascade="all, delete-orphan",
        foreign_keys="ChatMessage.topic_id",
    )

    __table_args__ = (
        Index("ix_chat_topics_channel_updated", "channel_id", "updated_at"),
    )

    def __repr__(self) -> str:
        return f"<ChatTopic {self.id}: {self.title[:30]}>"


class ChatMessage(Base):
    """
    Message in a channel or topic.

    If topic_id is set, the message belongs to that topic's discussion.
    If topic_id is null, it is general channel discussion.
    channel_id is always set for efficient queries.
    """
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_channels.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    topic_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("chat_topics.id", ondelete="CASCADE"),
        nullable=True, index=True
    )
    sender_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("chat_messages.id"), nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    mentioned_user_ids: Mapped[Optional[List[int]]] = mapped_column(
        JSON, nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    edited_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    channel = relationship("ChatChannel", back_populates="messages")
    topic = relationship(
        "ChatTopic", back_populates="messages", foreign_keys=[topic_id]
    )
    sender = relationship("User", backref="chat_messages")
    parent = relationship("ChatMessage", remote_side=[id], backref="replies")

    __table_args__ = (
        Index("ix_chat_messages_channel_id_msg", "channel_id", "id"),
        Index("ix_chat_messages_topic_id_msg", "topic_id", "id"),
        Index("ix_chat_messages_channel_created", "channel_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ChatMessage {self.id} by user {self.sender_id}>"


class DirectMessage(Base):
    """
    1:1 private message between two teachers.

    Independent of channels. Both users must be in the same organization.

    **Future group DMs (product TBD):** add ``DMConversation`` (stable id,
    optional ``title``), ``DMConversationMember`` (``conversation_id``,
    ``user_id``, ``last_read_message_id``, ``is_muted``), and either
    point ``DirectMessage.conversation_id`` at that row (nullable, with
    ``sender_id`` / ``recipient_id`` null for groups) or introduce
    ``GroupDirectMessage`` keyed by ``conversation_id`` only.  Unread
    then mirrors channel waterlines per member; list endpoints aggregate
    by conversation id (Zulip-style ``DirectMessageGroup`` + huddle hash).
    """
    __tablename__ = "direct_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sender_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    recipient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    mentioned_user_ids: Mapped[Optional[List[int]]] = mapped_column(
        JSON, nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    edited_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    sender = relationship("User", foreign_keys=[sender_id], backref="sent_dms")
    recipient = relationship("User", foreign_keys=[recipient_id], backref="received_dms")

    __table_args__ = (
        Index(
            "ix_direct_messages_pair",
            "sender_id", "recipient_id", "id",
        ),
        Index(
            "ix_direct_messages_recipient",
            "recipient_id", "sender_id", "id",
        ),
        Index("ix_direct_messages_created", "sender_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<DirectMessage {self.id}: {self.sender_id} -> {self.recipient_id}>"


class MessageReaction(Base):
    """
    Emoji reaction on a channel/topic message.

    Each user can add one instance of a given emoji per message.
    Stored as both a human-readable name and the Unicode codepoint.
    """
    __tablename__ = "message_reactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    message_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
    )
    emoji_name: Mapped[str] = mapped_column(String(50), nullable=False)
    emoji_code: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    message = relationship("ChatMessage", backref="reactions")
    user = relationship("User", backref="message_reactions")

    __table_args__ = (
        UniqueConstraint(
            "message_id", "user_id", "emoji_name",
            name="uq_message_reaction",
        ),
        Index("ix_message_reactions_message", "message_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<MessageReaction {self.id}: "
            f"msg={self.message_id} user={self.user_id} {self.emoji_code}>"
        )


class StarredMessage(Base):
    """
    User bookmark on a channel/topic message.

    A user can star a message to find it later.
    """
    __tablename__ = "starred_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    message_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    message = relationship("ChatMessage", backref="stars")
    user = relationship("User", backref="starred_messages_rel")

    __table_args__ = (
        UniqueConstraint(
            "message_id", "user_id", name="uq_starred_message",
        ),
        Index("ix_starred_messages_user", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<StarredMessage {self.id}: "
            f"msg={self.message_id} user={self.user_id}>"
        )


class FileAttachment(Base):
    """
    File attached to a channel message or direct message.

    Exactly one of ``message_id`` or ``dm_id`` should be set.
    Files are stored on disk under ``static/chat/``.
    """
    __tablename__ = "file_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    message_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    dm_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("direct_messages.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    uploader_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    message = relationship("ChatMessage", backref="attachments")
    dm = relationship("DirectMessage", backref="attachments")
    uploader = relationship("User", backref="uploaded_attachments")

    __table_args__ = (
        Index("ix_file_attachments_message", "message_id"),
        Index("ix_file_attachments_dm", "dm_id"),
    )

    def __repr__(self) -> str:
        return f"<FileAttachment {self.id}: {self.filename}>"


class UserTopicPreference(Base):
    """
    Per-user topic visibility preference (like Zulip's ``UserTopic``).

    Visibility policies:
    - ``inherit``: use the channel's default behaviour
    - ``muted``: hide notifications and unreads for this topic
    - ``unmuted``: override a muted channel to show this topic
    - ``followed``: higher-priority notifications for this topic
    """
    __tablename__ = "user_topic_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
    )
    topic_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_topics.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    visibility_policy: Mapped[str] = mapped_column(
        String(20), nullable=False, default="inherit",
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    user = relationship("User", backref="topic_preferences")
    topic = relationship("ChatTopic", backref="user_preferences")

    __table_args__ = (
        UniqueConstraint("user_id", "topic_id", name="uq_user_topic_pref"),
        CheckConstraint(
            "visibility_policy IN ('inherit', 'muted', 'unmuted', 'followed')",
            name="ck_user_topic_pref_policy",
        ),
        Index("ix_user_topic_prefs_user", "user_id", "topic_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserTopicPreference user={self.user_id} "
            f"topic={self.topic_id} policy={self.visibility_policy}>"
        )
