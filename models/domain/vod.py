"""Tencent Cloud VOD catalog rows (FileId + metadata only).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base

if TYPE_CHECKING:
    from models.domain.auth import Organization, User

VOD_STATUS_PENDING = "pending"
VOD_STATUS_PROCESSING = "processing"
VOD_STATUS_READY = "ready"
VOD_STATUS_FAILED = "failed"
VOD_STATUSES = frozenset(
    {
        VOD_STATUS_PENDING,
        VOD_STATUS_PROCESSING,
        VOD_STATUS_READY,
        VOD_STATUS_FAILED,
    }
)


def generate_vod_uuid() -> str:
    """Generate a UUID string for vod_media rows."""
    return str(uuid.uuid4())


class VodMedia(Base):
    """Org-owned Tencent VOD FileId catalog entry."""

    __tablename__ = "vod_media"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_vod_uuid, index=True)
    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    file_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=VOD_STATUS_PROCESSING, index=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cover_file_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    class_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_context: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    organization: Mapped["Organization"] = relationship("Organization", lazy="selectin")
    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id], lazy="selectin")

    __table_args__ = (
        UniqueConstraint("organization_id", "file_id", name="uq_vod_media_org_file_id"),
        Index("ix_vod_media_org_status_updated", "organization_id", "status", "updated_at"),
    )
