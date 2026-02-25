"""
Teacher Usage Classification Config Model
==========================================

Stores configurable thresholds for 2-tier teacher usage classification.
Scholars can tweak these via the Teacher Usage page UI.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.domain.auth import Base


def _default_thresholds() -> dict:
    """Default thresholds matching Table 2 (表2 现有平台教师使用行为)."""
    return {
        "continuous": {
            "active_weeks_min": 5,
            "active_weeks_first4_min": 1,
            "active_weeks_last4_min": 1,
            "max_zero_gap_days_max": 10,
        },
        "rejection": {
            "active_days_max": 3,
            "active_days_first10_min": 1,
            "active_days_last25_max": 0,
            "max_zero_gap_days_min": 25,
        },
        "stopped": {
            "active_days_first25_min": 3,
            "active_days_last14_max": 0,
            "max_zero_gap_days_min": 14,
        },
        "intermittent": {
            "n_bursts_min": 2,
            "internal_max_zero_gap_days_min": 7,
        },
    }


class TeacherUsageConfig(Base):
    """
    Single-row config for classification thresholds.

    Key 'classification_thresholds' stores JSON matching _default_thresholds().
    """
    __tablename__ = "teacher_usage_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    config_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    config_value: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
