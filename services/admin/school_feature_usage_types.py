"""Typed payloads for school-dashboard feature-usage analytics.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Literal, TypedDict

from services.admin.school_user_activity_types import SeriesPoint

CapacityKey = Literal["idle", "tense", "ample", "normal"]


class UsageBucket(TypedDict):
    """SQL-aggregated usage slice for one user / action / month."""

    user_id: int
    action: str
    title: str | None
    source: str
    success: bool
    month: str
    count: int


class TokenProcessBucket(TypedDict):
    """SQL-aggregated token_usage slice for duration and fail rate."""

    request_type: str
    endpoint_path: str
    calls: int
    failures: int
    duration_sum: float
    duration_count: int


class ModuleUsageRow(TypedDict):
    """One catalog module with access and process metrics."""

    key: str
    visits: int
    uses: int
    ops_per_visitor: float
    completed: int
    pass_rate: float
    fail_rate: float | None
    avg_duration_seconds: float | None
    capacity: CapacityKey
    monthly_uses: list[SeriesPoint]


class RankedModule(TypedDict):
    """Module key with optional usage-rate share."""

    key: str
    visits: int
    uses: int
    usage_rate: float | None


class BottleneckSlots(TypedDict):
    """Structured inputs for the bottleneck paragraph."""

    lowest_pass_keys: list[str]
    tense_keys: list[str]
    slow_keys: list[str]
    uniformly_high: bool
    no_bottleneck: bool


class ConclusionSlots(TypedDict):
    """Structured inputs for the judgement conclusion."""

    top_keys: list[str]
    idle_keys: list[str]
    concentrated: bool


class FeatureUsageJudgement(TypedDict):
    """研判 lists and template slots (no localized prose)."""

    top5: list[RankedModule]
    high: list[str]
    low: list[str]
    idle: list[str]
    bottleneck_slots: BottleneckSlots
    conclusion_slots: ConclusionSlots


class SchoolFeatureUsagePayload(TypedDict):
    """Full GET /admin/stats/school/feature-usage body."""

    year: int
    min_year: int
    generated_at: str
    enrolled: int
    modules: list[ModuleUsageRow]
    judgement: FeatureUsageJudgement
