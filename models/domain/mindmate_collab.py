"""
MindMate online collab (shared AI chatroom) domain models.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.domain.auth import Base


class MindmateCollabSession(Base):
    """Active or ended shared MindMate chatroom session."""

    __tablename__ = "mindmate_collab_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    organization_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )
    owner_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="MindMate Collab")
    dify_conversation_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="organization")
    duration_preset: Mapped[str] = mapped_column(String(16), nullable=False, default="today")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("code", name="uq_mindmate_collab_sessions_code"),
        Index(
            "ix_mindmate_collab_sessions_active_org",
            "organization_id",
            "visibility",
            postgresql_where=(ended_at.is_(None)),
        ),
    )


class MindmateCollabMessage(Base):
    """Persisted chat message in a MindMate collab room."""

    __tablename__ = "mindmate_collab_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("mindmate_collab_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_mindmate_collab_messages_session_created", "session_id", "created_at"),)
