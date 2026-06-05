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

from models.domain.auth import Organization, User
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


async def aggregate_mindbot_tokens_by_linked_user(
    db: AsyncSession,
    *,
    created_since: Optional[datetime] = None,
    organization_id: Optional[int] = None,
) -> Dict[int, TokenPeriodTotals]:
    """MindBot tokens keyed by linked MindGraph user id (when SSO linked)."""
    filters = _mindbot_usage_filters(
        created_since=created_since,
        organization_id=organization_id,
    )
    stmt = (
        select(
            MindbotUsageEvent.linked_user_id,
            sa_sum(_effective_input_expr()).label("input_tokens"),
            sa_sum(_effective_output_expr()).label("output_tokens"),
            sa_sum(_effective_total_expr()).label("total_tokens"),
            sql_count(MindbotUsageEvent.id).label("request_count"),
        )
        .where(filters, MindbotUsageEvent.linked_user_id.isnot(None))
        .group_by(MindbotUsageEvent.linked_user_id)
    )
    rows = (await db.execute(stmt)).all()
    by_user: Dict[int, TokenPeriodTotals] = {}
    for row in rows:
        if row.linked_user_id is None:
            continue
        by_user[int(row.linked_user_id)] = {
            "input_tokens": int(row.input_tokens or 0),
            "output_tokens": int(row.output_tokens or 0),
            "total_tokens": int(row.total_tokens or 0),
            "request_count": int(row.request_count or 0),
        }
    return by_user


async def aggregate_mindbot_tokens_by_linked_user_today(
    db: AsyncSession,
    today_start: datetime,
    organization_id: Optional[int] = None,
) -> Dict[int, TokenPeriodTotals]:
    """MindBot tokens for today keyed by linked MindGraph user id (when SSO linked)."""
    return await aggregate_mindbot_tokens_by_linked_user(
        db,
        created_since=today_start,
        organization_id=organization_id,
    )


async def merge_mindbot_tokens_into_top_user_rows(
    db: AsyncSession,
    rows: list[Dict[str, Any]],
    mindbot_by_user: Dict[int, TokenPeriodTotals],
    *,
    organization_id: Optional[int] = None,
    limit: int = 10,
    mask_phone: bool = False,
    include_org_name: bool = False,
    include_io_tokens: bool = False,
) -> list[Dict[str, Any]]:
    """Merge linked-user MindBot totals into ranking rows; promote MindBot-only users."""
    by_id: Dict[int, Dict[str, Any]] = {int(row["id"]): dict(row) for row in rows}
    for user_id, extra in mindbot_by_user.items():
        if user_id in by_id:
            row = by_id[user_id]
            row["input_tokens"] = int(row.get("input_tokens", 0)) + int(extra["input_tokens"])
            row["output_tokens"] = int(row.get("output_tokens", 0)) + int(extra["output_tokens"])
            row["total_tokens"] = int(row.get("total_tokens", 0)) + int(extra["total_tokens"])
            continue
        if int(extra.get("total_tokens", 0)) <= 0:
            continue
        user_stmt = (
            select(
                User.id,
                User.phone,
                User.name,
                Organization.name.label("organization_name"),
            )
            .outerjoin(Organization, User.organization_id == Organization.id)
            .where(User.id == user_id)
        )
        if organization_id is not None:
            user_stmt = user_stmt.where(User.organization_id == organization_id)
        user_row = (await db.execute(user_stmt)).first()
        if user_row is None:
            continue
        raw_phone = user_row.phone or ""
        phone = raw_phone
        if mask_phone and raw_phone and len(raw_phone) == 11:
            phone = raw_phone[:3] + "****" + raw_phone[-4:]
        display_name = user_row.name or raw_phone or str(user_row.id)
        if mask_phone and not user_row.name:
            display_name = phone or str(user_row.id)
        new_row: Dict[str, Any] = {
            "id": int(user_row.id),
            "phone": phone,
            "name": display_name,
            "total_tokens": int(extra["total_tokens"]),
        }
        if include_org_name:
            new_row["organization_name"] = user_row.organization_name or ""
        if include_io_tokens:
            new_row["input_tokens"] = int(extra["input_tokens"])
            new_row["output_tokens"] = int(extra["output_tokens"])
        by_id[user_id] = new_row

    merged = sorted(
        by_id.values(),
        key=lambda item: int(item.get("total_tokens", 0)),
        reverse=True,
    )
    return merged[:limit]


def merge_mindbot_daily_rows_into_tokens_by_date(
    tokens_by_date: MutableMapping[str, Dict[str, int]],
    mindbot_rows: list[Any],
    *,
    beijing_timezone: tzinfo,
) -> None:
    """Add MindBot daily rows into a trends ``tokens_by_date`` map (UTC date → Beijing key)."""
    from utils.auth.token_stats_queries import utc_date_to_beijing_key

    for row in mindbot_rows:
        beijing_date_str = utc_date_to_beijing_key(row.date, beijing_timezone)
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
    linked_user_id: Optional[int] = None,
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
    if linked_user_id is not None:
        stmt = stmt.where(MindbotUsageEvent.linked_user_id == linked_user_id)
    return list((await db.execute(stmt)).all())


async def aggregate_mindbot_tokens_by_hour(
    db: AsyncSession,
    *,
    created_since: datetime,
    organization_id: Optional[int] = None,
    linked_user_id: Optional[int] = None,
) -> Dict[str, Dict[str, int]]:
    """Hourly MindBot totals keyed by Beijing hour string (YYYY-MM-DD HH:00:00)."""
    from utils.auth.token_stats_queries import BEIJING_TIMEZONE

    filters = _mindbot_usage_filters(
        created_since=created_since,
        organization_id=organization_id,
    )
    stmt = (
        select(
            func.strftime("%Y-%m-%d %H:00:00", MindbotUsageEvent.created_at).label("datetime"),
            sa_sum(_effective_total_expr()).label("total_tokens"),
            sa_sum(_effective_input_expr()).label("input_tokens"),
            sa_sum(_effective_output_expr()).label("output_tokens"),
        )
        .where(filters)
        .group_by(func.strftime("%Y-%m-%d %H:00:00", MindbotUsageEvent.created_at))
    )
    if linked_user_id is not None:
        stmt = stmt.where(MindbotUsageEvent.linked_user_id == linked_user_id)
    rows = (await db.execute(stmt)).all()
    tokens_by_hour: Dict[str, Dict[str, int]] = {}
    for row in rows:
        utc_datetime = datetime.strptime(row.datetime, "%Y-%m-%d %H:00:00")
        utc_datetime = utc_datetime.replace(tzinfo=timezone.utc)
        beijing_hour_str = utc_datetime.astimezone(BEIJING_TIMEZONE).strftime("%Y-%m-%d %H:00:00")
        if beijing_hour_str not in tokens_by_hour:
            tokens_by_hour[beijing_hour_str] = {"total": 0, "input": 0, "output": 0}
        tokens_by_hour[beijing_hour_str]["total"] += int(row.total_tokens or 0)
        tokens_by_hour[beijing_hour_str]["input"] += int(row.input_tokens or 0)
        tokens_by_hour[beijing_hour_str]["output"] += int(row.output_tokens or 0)
    return tokens_by_hour


def merge_mindbot_hourly_into_tokens_by_hour(
    tokens_by_hour: MutableMapping[str, Dict[str, int]],
    mindbot_by_hour: Dict[str, Dict[str, int]],
) -> None:
    """Add MindBot hourly buckets into an existing hour map."""
    for hour_str, extra in mindbot_by_hour.items():
        if hour_str not in tokens_by_hour:
            tokens_by_hour[hour_str] = {"total": 0, "input": 0, "output": 0}
        tokens_by_hour[hour_str]["total"] += int(extra.get("total", 0))
        tokens_by_hour[hour_str]["input"] += int(extra.get("input", 0))
        tokens_by_hour[hour_str]["output"] += int(extra.get("output", 0))
