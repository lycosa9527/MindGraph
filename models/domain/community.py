"""
Community Models for MindGraph

Database models for global community content sharing.
Posts are visible to all users; thumbnails stored as files on disk.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base


def generate_uuid() -> str:
    """Generate a UUID string for community post IDs."""
    return str(uuid.uuid4())


class CommunityPost(Base):
    """
    Community post model for global sharing.

    Represents MindGraph diagrams shared to the public community.
    Thumbnail stored as file at static/community/{id}.png.
    """

    __tablename__ = "community_posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid, index=True)

    # Content
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    diagram_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    spec: Mapped[dict] = mapped_column(pg.JSONB, nullable=False)

    # Thumbnail path (e.g. community/uuid.png) - file on disk
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Author
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Engagement
    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    author: Mapped["User"] = relationship("User", lazy="selectin")

    __table_args__ = (
        Index("ix_community_posts_author_created", "author_id", "created_at"),
        Index("ix_community_posts_category", "category"),
        Index("ix_community_posts_created", "created_at"),
    )


class CommunityPostLike(Base):
    """Tracks user likes on community posts. One like per user per post."""

    __tablename__ = "community_post_likes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[str] = mapped_column(String(36), ForeignKey("community_posts.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
    )

    post: Mapped["CommunityPost"] = relationship("CommunityPost", lazy="selectin")
    user: Mapped["User"] = relationship("User", lazy="selectin")

    __table_args__ = (Index("ix_community_post_likes_unique", "post_id", "user_id", unique=True),)


class CommunityPostComment(Base):
    """Comments on community posts."""

    __tablename__ = "community_post_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[str] = mapped_column(String(36), ForeignKey("community_posts.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
    )

    post: Mapped["CommunityPost"] = relationship("CommunityPost", lazy="selectin")
    user: Mapped["User"] = relationship("User", lazy="selectin")

    __table_args__ = (Index("ix_community_post_comments_post", "post_id", "created_at"),)
