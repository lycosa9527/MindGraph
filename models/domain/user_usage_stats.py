"""
User Usage Stats Model
======================

Stores pre-computed teacher usage metrics and 2-tier classification.
Avoids runtime recomputation when serving the teacher usage API.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.domain.auth import Base


class UserUsageStats(Base):
    """
    Pre-computed usage stats per user for teacher classification.

    Metrics are computed from token_usage and user_activity_log.
    Updated on login and token usage (async).
    """
    __tablename__ = "user_usage_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    active_days: Mapped[int] = mapped_column(Integer, default=0)
    active_days_first10: Mapped[int] = mapped_column(Integer, default=0)
    active_days_last25: Mapped[int] = mapped_column(Integer, default=0)
    active_days_first25: Mapped[int] = mapped_column(Integer, default=0)
    active_days_last14: Mapped[int] = mapped_column(Integer, default=0)
    active_weeks: Mapped[int] = mapped_column(Integer, default=0)
    active_weeks_first4: Mapped[int] = mapped_column(Integer, default=0)
    active_weeks_last4: Mapped[int] = mapped_column(Integer, default=0)
    max_zero_gap_days: Mapped[int] = mapped_column(Integer, default=0)
    n_bursts: Mapped[int] = mapped_column(Integer, default=0)
    internal_max_zero_gap_days: Mapped[int] = mapped_column(Integer, default=0)

    tier1: Mapped[str] = mapped_column(String(50), nullable=False, default="unused")
    tier2: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("idx_user_usage_stats_tier1_tier2", "tier1", "tier2"),
    )
