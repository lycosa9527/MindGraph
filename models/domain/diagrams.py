"""
Diagram Storage Models for MindGraph
=====================================

Database model for user-created diagrams with persistent storage.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import UTC, datetime
from typing import Optional
import uuid

from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base


def generate_uuid() -> str:
    """Generate a UUID string for diagram IDs."""
    return str(uuid.uuid4())


class Diagram(Base):
    """
    User-created diagrams for persistent storage and editing.

    Stores the diagram spec as JSONB for native PostgreSQL indexing and partial updates.
    Supports soft delete for data recovery.
    Uses UUID for secure, non-guessable diagram IDs.
    """

    __tablename__ = "diagrams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Metadata (queryable)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    diagram_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(10), default="zh")

    # The actual diagram data — stored as JSONB for native parsing and GIN indexing.
    spec: Mapped[dict] = mapped_column(pg.JSONB, nullable=False)

    # Optional: thumbnail for gallery view (base64 data URL)
    thumbnail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Soft delete support
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Pin support - pinned diagrams appear at top
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Workshop support - shareable code for collaborative editing
    workshop_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    # organization = 校内 (same-org / list join); network = 共同 (code + any authenticated user)
    workshop_visibility: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    # Collaborative session window (naive UTC); None = legacy row before migration / backfill
    workshop_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    workshop_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    workshop_duration_preset: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="diagrams", lazy="selectin")
    snapshots: Mapped[list["DiagramSnapshot"]] = relationship(
        "DiagramSnapshot",
        back_populates="diagram",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Composite index for efficient queries
    __table_args__ = (Index("ix_diagrams_user_updated", "user_id", "updated_at", "is_deleted"),)

    def __repr__(self) -> str:
        return f"<Diagram {self.id}: {self.title} ({self.diagram_type})>"
