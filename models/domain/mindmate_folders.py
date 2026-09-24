"""
MindMate archive folders for organizing Dify conversations.

Conversations themselves stay in Dify. Folder names and membership live here,
the same way pinned conversations are tracked locally.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base

if TYPE_CHECKING:
    from models.domain.auth import User


def generate_mindmate_folder_uuid() -> str:
    """Generate a UUID string for MindMate folder IDs."""
    return str(uuid.uuid4())


class MindmateFolder(Base):
    """User-owned folder for organizing MindMate conversations."""

    __tablename__ = "mindmate_folders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_mindmate_folder_uuid)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    user: Mapped["User"] = relationship("User", back_populates="mindmate_folders", lazy="selectin")
    placements: Mapped[list["MindmateConversationFolder"]] = relationship(
        "MindmateConversationFolder",
        back_populates="folder",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="select",
    )

    __table_args__ = (Index("ix_mindmate_folders_user_sort", "user_id", "sort_order"),)

    def __repr__(self) -> str:
        return f"<MindmateFolder {self.id}: {self.name}>"


class MindmateConversationFolder(Base):
    """Maps one Dify conversation id to a MindMate folder for a user."""

    __tablename__ = "mindmate_conversation_folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    folder_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("mindmate_folders.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    folder: Mapped["MindmateFolder"] = relationship(
        "MindmateFolder",
        back_populates="placements",
        lazy="select",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "conversation_id", name="uq_mindmate_conv_folder_user_conv"),
        Index("ix_mindmate_conv_folder_folder", "folder_id"),
    )

    def __repr__(self) -> str:
        return f"<MindmateConversationFolder user={self.user_id} conv={self.conversation_id}>"
