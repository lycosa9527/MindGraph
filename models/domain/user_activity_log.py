"""
User Activity Log Model
======================

Persists login and other user activity events for days-active computation.
Used for teacher usage analytics (distinct days with activity).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.domain.auth import Base


class UserActivityLog(Base):
    """
    User activity log for login and other events.

    Each row represents one activity event (e.g. login).
    Used to compute distinct days active for teacher usage classification.
    """

    __tablename__ = "user_activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False, default="login")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (Index("idx_user_activity_log_user_date", "user_id", "created_at"),)
