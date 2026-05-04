"""
School Zone Models for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Database models for organization-scoped content sharing.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base

if TYPE_CHECKING:
    from models.domain.auth import Organization, User


def generate_uuid() -> str:
    """Generate a UUID string for shared diagram IDs."""
    return str(uuid.uuid4())


class SharedDiagram(Base):
    """
    Shared Diagram model for organization-scoped sharing

    Represents diagrams or MindMate courses shared within an organization.
    Only users from the same organization can view shared content.
    Uses UUID for secure, non-guessable IDs.
    """

    __tablename__ = "shared_diagrams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid, index=True)

    # Content info
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'mindgraph' or 'mindmate'
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., '教学设计', '学科资源'

    # The actual diagram data — stored as JSONB for native parsing and GIN indexing.
    diagram_data: Mapped[Optional[dict]] = mapped_column(pg.JSONB, nullable=True)

    # Thumbnail/preview (base64 or URL)
    thumbnail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Organization scope - content is only visible within this organization
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)

    # Author info
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Engagement metrics
    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    shares_count: Mapped[int] = mapped_column(Integer, default=0)
    views_count: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # Soft delete support

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", lazy="selectin")
    author: Mapped["User"] = relationship("User", lazy="selectin")

    # Composite index for efficient organization-scoped queries
    __table_args__ = (
        Index("ix_shared_diagrams_org_created", "organization_id", "created_at"),
        Index("ix_shared_diagrams_org_category", "organization_id", "category"),
    )


class SharedDiagramLike(Base):
    """
    Tracks user likes on shared diagrams.
    One like per user per diagram.
    """

    __tablename__ = "shared_diagram_likes"

    id = Column(Integer, primary_key=True, index=True)
    diagram_id = Column(String(36), ForeignKey("shared_diagrams.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    # Relationships
    diagram = relationship("SharedDiagram", lazy="selectin")
    user = relationship("User", lazy="selectin")

    # Unique constraint: one like per user per diagram
    __table_args__ = (Index("ix_shared_diagram_likes_unique", "diagram_id", "user_id", unique=True),)


class SharedDiagramComment(Base):
    """
    Comments on shared diagrams.
    """

    __tablename__ = "shared_diagram_comments"

    id = Column(Integer, primary_key=True, index=True)
    diagram_id = Column(String(36), ForeignKey("shared_diagrams.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Status
    is_active = Column(Boolean, default=True)  # Soft delete support

    # Relationships
    diagram = relationship("SharedDiagram", lazy="selectin")
    user = relationship("User", lazy="selectin")
