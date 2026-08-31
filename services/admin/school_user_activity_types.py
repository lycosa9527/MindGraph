"""Typed payloads for school-dashboard user activity analytics.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict


class SeriesPoint(TypedDict):
    """One labeled numeric point for a chart series."""

    date: str
    value: int


class HourPoint(TypedDict):
    """Login count for one Beijing hour of day."""

    hour: int
    value: int


class BucketPoint(TypedDict):
    """Histogram bucket for login-count distribution."""

    label: str
    value: int


class OrgUserStamp(TypedDict):
    """Org member used for activity aggregation."""

    user_id: int
    created_at: datetime


class LoginStamp(TypedDict):
    """Login event used for activity aggregation."""

    user_id: int
    created_at: datetime


class TotalsBlock(TypedDict):
    """User-total cards."""

    cumulative_registered: int
    year_new_users: int
    churn_available: bool
    enrolled_today: int
    cumulative_series: list[SeriesPoint]
    year_new_series: list[SeriesPoint]
    enrolled_series: list[SeriesPoint]


class ActivityBlock(TypedDict):
    """Active-user cards."""

    daily_active: list[SeriesPoint]
    monthly_active: list[SeriesPoint]
    quarterly_active: list[SeriesPoint]
    avg_daily_active: float
    avg_monthly_active: float


class FrequencyBlock(TypedDict):
    """Login-frequency cards."""

    login_count_buckets: list[BucketPoint]
    high_freq_count: int
    high_freq_share: float
    low_freq_count: int
    low_freq_share: float
    hour_of_day: list[HourPoint]


class SchoolUserActivityPayload(TypedDict):
    """Full GET /admin/stats/school/user-activity body."""

    year: int
    min_year: int
    generated_at: str
    totals: TotalsBlock
    activity: ActivityBlock
    frequency: FrequencyBlock
