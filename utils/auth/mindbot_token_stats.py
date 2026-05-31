"""Aggregate MindBot (DingTalk / Dify) usage into admin token statistics.

DingTalk bot traffic uses the same Dify stack as web MindMate but is stored in
``mindbot_usage_events``. These helpers fold that usage into platform totals and
the MindMate service bucket.
"""

from __future__ import annotations

from datetime import datetime, timezone, tzinfo
from typing import Any, Dict, MutableMapping, Optional, TypedDict

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.functions import coalesce as sa_coalesce
from sqlalchemy.sql.functions import count as sql_count
from sqlalchemy.sql.functions import sum as sa_sum

from models.domain.auth import Organization
from models.domain.mindbot_usage import MindbotUsageEvent
from services.mindbot.errors import MindbotErrorCode

MINDBOT_USAGE_SUCCESS_CODES = (
    MindbotErrorCode.OK.value,
    MindbotErrorCode.ACCEPTED.value,
)


class TokenPeriodTotals(TypedDict):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_count: int


def empty_token_period() -> TokenPeriodTotals:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "request_count": 0,
    }


def _effective_input_expr() -> ColumnElement:
    return sa_coalesce(MindbotUsageEvent.prompt_tokens, 0)


def _effective_output_expr() -> ColumnElement:
    return sa_coalesce(MindbotUsageEvent.completion_tokens, 0)


def _effective_total_expr() -> ColumnElement:
    return sa_coalesce(
        MindbotUsageEvent.total_tokens,
        sa_coalesce(MindbotUsageEvent.prompt_tokens, 0)
        + sa_coalesce(MindbotUsageEvent.completion_tokens, 0),
        0,
    )


def _mindbot_usage_filters(
    *,
    created_since: Optional[datetime] = None,
    organization_id: Optional[int] = None,
) -> ColumnElement:
    clauses = [
        MindbotUsageEvent.error_code.in_(MINDBOT_USAGE_SUCCESS_CODES),
        or_(
            MindbotUsageEvent.total_tokens > 0,
            MindbotUsageEvent.prompt_tokens > 0,
            MindbotUsageEvent.completion_tokens > 0,
        ),
    ]
    if created_since is not None:
        clauses.append(MindbotUsageEvent.created_at >= created_since)
    if organization_id is not None:
        clauses.append(MindbotUsageEvent.organization_id == organization_id)
    return and_(*clauses)


def add_token_period(
    base: Dict[str, int],
    extra: TokenPeriodTotals,
) -> Dict[str, int]:
    """Merge MindBot totals into a token-stats period dict (input/output/total only)."""
    return {
        "input_tokens": int(base.get("input_tokens", 0)) + extra["input_tokens"],
        "output_tokens": int(base.get("output_tokens", 0)) + extra["output_tokens"],
        "total_tokens": int(base.get("total_tokens", 0)) + extra["total_tokens"],
    }


def add_service_period(
    base: Dict[str, int],
    extra: TokenPeriodTotals,
) -> Dict[str, int]:
    """Merge MindBot totals into a by_service period dict (includes request_count)."""
    merged = add_token_period(base, extra)
    merged["request_count"] = int(base.get("request_count", 0)) + extra["request_count"]
    return merged


def merge_org_token_stats(
    base: Dict[str, Dict[str, Any]],
    extra: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Merge per-organization MindBot stats into TokenUsage org rankings."""
    merged = dict(base)
    for org_name, stats in extra.items():
        if org_name in merged:
            existing = merged[org_name]
            merged[org_name] = {
                "org_id": existing.get("org_id") or stats.get("org_id"),
                "input_tokens": int(existing.get("input_tokens", 0)) + int(stats.get("input_tokens", 0)),
                "output_tokens": int(existing.get("output_tokens", 0)) + int(stats.get("output_tokens", 0)),
                "total_tokens": int(existing.get("total_tokens", 0)) + int(stats.get("total_tokens", 0)),
                "request_count": int(existing.get("request_count", 0)) + int(stats.get("request_count", 0)),
            }
        else:
            merged[org_name] = dict(stats)
    return merged


async def aggregate_mindbot_token_totals(
    db: AsyncSession,
    *,
    created_since: Optional[datetime] = None,
    organization_id: Optional[int] = None,
) -> TokenPeriodTotals:
    """Sum MindBot Dify token usage for one time window (and optional org)."""
    stmt = select(
        sa_sum(_effective_input_expr()).label("input_tokens"),
        sa_sum(_effective_output_expr()).label("output_tokens"),
        sa_sum(_effective_total_expr()).label("total_tokens"),
        sql_count(MindbotUsageEvent.id).label("request_count"),
    ).where(
        _mindbot_usage_filters(
            created_since=created_since,
            organization_id=organization_id,
        )
    )
    row = (await db.execute(stmt)).first()
    if not row:
        return empty_token_period()
    return {
        "input_tokens": int(row.input_tokens or 0),
        "output_tokens": int(row.output_tokens or 0),
        "total_tokens": int(row.total_tokens or 0),
        "request_count": int(row.request_count or 0),
    }


async def aggregate_mindbot_tokens_by_org_today(
    db: AsyncSession,
    today_start: datetime,
) -> Dict[str, Dict[str, Any]]:
    """Per-organization MindBot token usage for the current Beijing calendar day."""
    rows = (
        await db.execute(
            select(
                Organization.id,
                Organization.name,
                sa_coalesce(sa_sum(_effective_input_expr()), 0).label("input_tokens"),
                sa_coalesce(sa_sum(_effective_output_expr()), 0).label("output_tokens"),
                sa_coalesce(sa_sum(_effective_total_expr()), 0).label("total_tokens"),
                sa_coalesce(sql_count(MindbotUsageEvent.id), 0).label("request_count"),
            )
            .select_from(MindbotUsageEvent)
            .join(Organization, Organization.id == MindbotUsageEvent.organization_id)
            .where(_mindbot_usage_filters(created_since=today_start))
            .group_by(Organization.id, Organization.name)
        )
    ).all()

    by_org: Dict[str, Dict[str, Any]] = {}
    for org_stat in rows:
        if org_stat.request_count and org_stat.request_count > 0:
            by_org[org_stat.name] = {
                "org_id": org_stat.id,
                "input_tokens": int(org_stat.input_tokens or 0),
                "output_tokens": int(org_stat.output_tokens or 0),
                "total_tokens": int(org_stat.total_tokens or 0),
                "request_count": int(org_stat.request_count or 0),
            }
    return by_org


def merge_mindbot_daily_rows_into_tokens_by_date(
    tokens_by_date: MutableMapping[str, Dict[str, int]],
    mindbot_rows: list[Any],
    *,
    beijing_timezone: tzinfo,
) -> None:
    """Add MindBot daily rows into a trends ``tokens_by_date`` map (UTC date → Beijing key)."""
    for row in mindbot_rows:
        utc_date = row.date
        if isinstance(utc_date, str):
            utc_date = datetime.strptime(utc_date, "%Y-%m-%d").date()
        utc_datetime = datetime.combine(utc_date, datetime.min.time())
        beijing_datetime = utc_datetime.replace(tzinfo=timezone.utc).astimezone(beijing_timezone)
        beijing_date_str = str(beijing_datetime.date())
        if beijing_date_str not in tokens_by_date:
            tokens_by_date[beijing_date_str] = {"total": 0, "input": 0, "output": 0}
        tokens_by_date[beijing_date_str]["total"] += int(row.total_tokens or 0)
        tokens_by_date[beijing_date_str]["input"] += int(row.input_tokens or 0)
        tokens_by_date[beijing_date_str]["output"] += int(row.output_tokens or 0)


async def aggregate_mindbot_tokens_by_date(
    db: AsyncSession,
    *,
    created_since: datetime,
    organization_id: Optional[int] = None,
) -> list[Any]:
    """Daily MindBot token sums keyed by UTC date (same shape as token trends query)."""
    stmt = (
        select(
            func.date(MindbotUsageEvent.created_at).label("date"),
            sa_sum(_effective_total_expr()).label("total_tokens"),
            sa_sum(_effective_input_expr()).label("input_tokens"),
            sa_sum(_effective_output_expr()).label("output_tokens"),
        )
        .where(
            _mindbot_usage_filters(
                created_since=created_since,
                organization_id=organization_id,
            )
        )
        .group_by(func.date(MindbotUsageEvent.created_at))
    )
    return list((await db.execute(stmt)).all())
