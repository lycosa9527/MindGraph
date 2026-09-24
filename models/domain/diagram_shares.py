"""
Library grants so one diagram can appear in several org members' libraries.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.domain.auth import Base


class DiagramShare(Base):
    """One recipient's place in the library for a diagram they do not own."""

    __tablename__ = "diagram_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    diagram_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("diagrams.id", ondelete="CASCADE"),
        nullable=False,
    )
    grantee_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    shared_by_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    folder_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("diagram_folders.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("diagram_id", "grantee_user_id", name="uq_diagram_shares_diagram_grantee"),
        Index("ix_diagram_shares_grantee", "grantee_user_id"),
    )

    def __repr__(self) -> str:
        return f"<DiagramShare diagram={self.diagram_id} grantee={self.grantee_user_id}>"
