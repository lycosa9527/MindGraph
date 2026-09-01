"""Load org members and usage buckets, then assemble feature-usage cards.

Uses the caller's panel-RLS session. Does not open a new engine or system session.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from models.domain.token_usage import TokenUsage
from models.domain.user_usage_activity import UserUsageActivity
from services.admin.school_feature_usage_compute import build_judgement, build_module_rows
from services.admin.school_feature_usage_types import (
    SchoolFeatureUsagePayload,
    TokenProcessBucket,
    UsageBucket,
)
from services.admin.school_user_activity_compute import min_activity_year, year_bounds
from services.admin.school_user_activity_stats import beijing_now, load_org_users


def _beijing_month_expr() -> ColumnElement[str]:
    """YYYY-MM in Asia/Shanghai from a timestamptz column."""
    return func.to_char(func.timezone("Asia/Shanghai", UserUsageActivity.created_at), "YYYY-MM")


async def load_usage_buckets(
    db: AsyncSession,
    user_ids: list[int],
    year: int,
) -> list[UsageBucket]:
    """Aggregate usage events for current members in the selected Beijing year."""
    if not user_ids:
        return []
    year_start, year_end = year_bounds(year)
    start_utc = year_start.astimezone(UTC)
    end_utc = year_end.astimezone(UTC)
    month_key = _beijing_month_expr()
    rows = (
        await db.execute(
            select(
                UserUsageActivity.user_id,
                UserUsageActivity.action,
                UserUsageActivity.title,
                UserUsageActivity.source,
                UserUsageActivity.success,
                month_key,
                func.count(),
            )
            .where(
                UserUsageActivity.user_id.in_(user_ids),
                UserUsageActivity.created_at >= start_utc,
                UserUsageActivity.created_at < end_utc,
            )
            .group_by(
                UserUsageActivity.user_id,
                UserUsageActivity.action,
                UserUsageActivity.title,
                UserUsageActivity.source,
                UserUsageActivity.success,
                month_key,
            )
        )
    ).all()
    buckets: list[UsageBucket] = []
    for user_id, action, title, source, success, month, count in rows:
        buckets.append(
            {
                "user_id": int(user_id),
                "action": str(action or ""),
                "title": str(title) if title else None,
                "source": str(source or ""),
                "success": bool(success),
                "month": str(month or ""),
                "count": int(count),
            }
        )
    return buckets


def _naive_utc(value: datetime) -> datetime:
    """token_usage.created_at is timezone-naive UTC."""
    return value.astimezone(UTC).replace(tzinfo=None)


async def load_token_buckets(
    db: AsyncSession,
    user_ids: list[int],
    year: int,
) -> list[TokenProcessBucket]:
    """Aggregate LLM duration and failures for current members in the Beijing year."""
    if not user_ids:
        return []
    year_start, year_end = year_bounds(year)
    start_utc = _naive_utc(year_start)
    end_utc = _naive_utc(year_end)
    duration_positive = TokenUsage.response_time > 0
    rows = (
        await db.execute(
            select(
                TokenUsage.request_type,
                TokenUsage.endpoint_path,
                func.count(),
                func.coalesce(
                    func.sum(case((TokenUsage.success.is_(False), 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(case((duration_positive, TokenUsage.response_time), else_=0.0)),
                    0.0,
                ),
                func.coalesce(
                    func.sum(case((duration_positive, 1), else_=0)),
                    0,
                ),
            )
            .where(
                TokenUsage.user_id.in_(user_ids),
                TokenUsage.created_at >= start_utc,
                TokenUsage.created_at < end_utc,
            )
            .group_by(TokenUsage.request_type, TokenUsage.endpoint_path)
        )
    ).all()
    buckets: list[TokenProcessBucket] = []
    for request_type, endpoint_path, calls, failures, duration_sum, duration_count in rows:
        buckets.append(
            {
                "request_type": str(request_type or ""),
                "endpoint_path": str(endpoint_path or ""),
                "calls": int(calls),
                "failures": int(failures),
                "duration_sum": float(duration_sum),
                "duration_count": int(duration_count),
            }
        )
    return buckets


def assemble_payload(
    user_ids: list[int],
    buckets: list[UsageBucket],
    year: int,
    min_year: int,
    now_beijing: datetime,
    token_buckets: list[TokenProcessBucket] | None = None,
) -> SchoolFeatureUsagePayload:
    """Assemble the API payload from already-loaded rows."""
    modules = build_module_rows(buckets, year, token_buckets or [])
    enrolled = len(user_ids)
    generated = now_beijing.astimezone(UTC)
    return {
        "year": year,
        "min_year": min_year,
        "generated_at": generated.isoformat().replace("+00:00", "Z"),
        "enrolled": enrolled,
        "modules": modules,
        "judgement": build_judgement(modules, enrolled),
    }


async def build_school_feature_usage(
    db: AsyncSession,
    organization_id: int,
    year: int | None,
) -> SchoolFeatureUsagePayload:
    """Fetch org-scoped usage and return the feature-usage dashboard payload.

    Raises ValueError with ``invalid_year`` or ``year_out_of_range`` when the
    requested year is not allowed.
    """
    now = beijing_now()
    users = await load_org_users(db, organization_id)
    lowest = min_activity_year(users, now.year)
    selected = now.year if year is None else year
    if selected > now.year:
        raise ValueError("invalid_year")
    if selected < lowest:
        raise ValueError("year_out_of_range")
    user_ids = [row["user_id"] for row in users]
    if not user_ids:
        return assemble_payload([], [], selected, lowest, now, [])
    buckets = await load_usage_buckets(db, user_ids, selected)
    token_buckets = await load_token_buckets(db, user_ids, selected)
    return assemble_payload(user_ids, buckets, selected, lowest, now, token_buckets)
