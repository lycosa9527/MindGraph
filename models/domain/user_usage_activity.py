"""
User usage activity rows for admin activity timeline (MindGraph / MindMate / DingTalk).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.domain.auth import Base


class UserUsageActivity(Base):
    """Curated per-user activity event with human-readable previews for admin UI."""

    __tablename__ = "user_usage_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    prompt_preview: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reply_preview: Mapped[str | None] = mapped_column(String(120), nullable=True)
    diagram_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    diagram_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("diagrams.id", ondelete="SET NULL"),
        nullable=True,
    )
    conversation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_user_usage_activities_user_id_desc", "user_id", "id"),
        Index("ix_user_usage_activities_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<UserUsageActivity user={self.user_id} source={self.source!r} action={self.action!r} id={self.id}>"
