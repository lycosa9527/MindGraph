"""
Persisted application error events and fingerprint groups for admin error collection.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base


class ErrorGroup(Base):
    """Aggregated error fingerprint (Sentry-style grouping)."""

    __tablename__ = "error_groups"
    __table_args__ = (
        Index("ix_error_groups_fingerprint", "fingerprint", unique=True),
        Index("ix_error_groups_last_seen", "last_seen_at"),
        Index("ix_error_groups_severity", "severity"),
        Index("ix_error_groups_source", "source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="error")
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    component: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    exception_type: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    sample_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    muted: Mapped[bool] = mapped_column(default=False, nullable=False)

    events = relationship("ErrorEvent", back_populates="group", lazy="select")


class ErrorEvent(Base):
    """Single captured error occurrence."""

    __tablename__ = "error_events"
    __table_args__ = (
        Index("ix_error_events_created_at", "created_at"),
        Index("ix_error_events_group_id", "group_id"),
        Index("ix_error_events_severity", "severity"),
        Index("ix_error_events_source", "source"),
        Index("ix_error_events_fingerprint", "fingerprint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("error_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="error")
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    component: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    exception_type: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stacktrace: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    http_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    group = relationship("ErrorGroup", back_populates="events", lazy="select")
