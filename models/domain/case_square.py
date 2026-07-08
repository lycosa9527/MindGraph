"""
Case Square models — moderated public teaching case gallery.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base

if TYPE_CHECKING:
    from models.domain.auth import User


def generate_case_uuid() -> str:
    """Generate a UUID string for case square post IDs."""
    return str(uuid.uuid4())


class CaseSquarePost(Base):
    """Public teaching case in the Case Square gallery."""

    __tablename__ = "case_square_posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_case_uuid, index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(pg.JSONB, nullable=False, default=list)

    # teaching_design | diagram_case | diagram_template
    case_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    subject: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    grade: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    diagram_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    spec: Mapped[Optional[dict]] = mapped_column(pg.JSONB, nullable=True)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    submitted_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    publish_source: Mapped[str] = mapped_column(String(20), nullable=False, default="self", index=True)
    attribution: Mapped[Optional[dict]] = mapped_column(pg.JSONB, nullable=True)

    # pending | approved | rejected | withdrawn
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    is_expert_recommended: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    expert_recommended_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    expert_recommended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    reviewed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    views_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    author: Mapped["User"] = relationship("User", foreign_keys=[author_id], lazy="selectin")
    reviewer: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reviewed_by], lazy="selectin")
    expert_recommender: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[expert_recommended_by], lazy="selectin"
    )

    __table_args__ = (
        Index("ix_case_square_posts_status_created", "status", "created_at"),
        Index("ix_case_square_posts_expert_created", "is_expert_recommended", "created_at"),
    )


class CaseSquarePostLike(Base):
    """User likes on case square posts."""

    __tablename__ = "case_square_post_likes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[str] = mapped_column(String(36), ForeignKey("case_square_posts.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    post: Mapped["CaseSquarePost"] = relationship("CaseSquarePost", lazy="selectin")
    user: Mapped["User"] = relationship("User", lazy="selectin")

    __table_args__ = (Index("ix_case_square_post_likes_unique", "post_id", "user_id", unique=True),)


class CaseSquarePostFavorite(Base):
    """User favorites (bookmarks) on case square posts."""

    __tablename__ = "case_square_post_favorites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[str] = mapped_column(String(36), ForeignKey("case_square_posts.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    post: Mapped["CaseSquarePost"] = relationship("CaseSquarePost", lazy="selectin")
    user: Mapped["User"] = relationship("User", lazy="selectin")

    __table_args__ = (Index("ix_case_square_post_favorites_unique", "post_id", "user_id", unique=True),)
