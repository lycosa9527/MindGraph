"""
Dashboard Activity Model
========================

Stores activity history for the public dashboard.
Activities are persisted to database for history retention across page refreshes.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.domain.auth import Base


class DashboardActivity(Base):
    """
    Dashboard activity history model.

    Stores user activities displayed in the public dashboard activity panel.
    Activities persist across page refreshes and are kept for historical analysis.
    """

    __tablename__ = "dashboard_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Activity details
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    diagram_type: Mapped[str] = mapped_column(String(50), nullable=False)
    topic: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    # Index for efficient queries (most recent first)
    __table_args__ = (Index("idx_dashboard_activities_created_at", "created_at"),)
