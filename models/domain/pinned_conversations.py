"""
Pinned Conversations Model for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Database model for tracking pinned MindMate conversations.
Since MindMate conversations are stored in Dify (external service),
we track pinned status in our own database.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base

if TYPE_CHECKING:
    from models.domain.auth import User


class PinnedConversation(Base):
    """
    Tracks pinned MindMate conversations for users.

    Each record represents a pinned conversation for a specific user.
    The conversation_id references the Dify conversation ID (UUID string).
    """

    __tablename__ = "pinned_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    pinned_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    dify_user: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    channel: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    server: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mindbot_config_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship("User", backref="pinned_conversations", lazy="selectin")

    __table_args__ = (Index("ix_pinned_conv_user_conv", "user_id", "conversation_id", unique=True),)
