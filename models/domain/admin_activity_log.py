"""
Admin activity log
==================

One row per successful management-panel write by a non-regular user
(superadmin, teaching researcher, expert, school manager).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.domain.auth import Base


class AdminActivityLog(Base):
    """Immutable record of a privileged admin write."""

    __tablename__ = "admin_activity_log"
    __table_args__ = (
        Index("ix_admin_activity_log_created_at", "created_at"),
        Index("ix_admin_activity_log_action", "action"),
        Index("ix_admin_activity_log_actor_role", "actor_role"),
        Index("ix_admin_activity_log_actor_user_id", "actor_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_label: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    http_method: Mapped[str] = mapped_column(String(8), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    detail: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    client_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
