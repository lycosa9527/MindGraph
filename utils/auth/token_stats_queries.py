"""Shared SQL helpers for admin token statistics and trends."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import Any, Optional, TypedDict

from sqlalchemy import or_
from sqlalchemy.sql.elements import ColumnElement

from models.domain.token_usage import TokenUsage

BEIJING_TIMEZONE = timezone(timedelta(hours=8))


class BeijingPeriodStarts(TypedDict):
    today_start: datetime
    week_ago: datetime
    month_ago: datetime
    beijing_today_start: datetime


def token_usage_service_filter(service: Optional[str]) -> Optional[ColumnElement]:
    """Filter TokenUsage rows by MindGraph vs MindMate (matches token-stats breakdown)."""
    if service == "mindmate":
        return TokenUsage.request_type == "mindmate"
    if service == "mindgraph":
        return or_(
            TokenUsage.request_type != "mindmate",
            TokenUsage.request_type.is_(None),
        )
    return None


def apply_token_service_filter(stmt: Any, service: Optional[str]) -> Any:
    """Apply service filter to a SQLAlchemy select (trends endpoints)."""
    service_filter = token_usage_service_filter(service)
    if service_filter is not None:
        return stmt.where(service_filter)
    return stmt


def beijing_period_starts(beijing_now: datetime) -> BeijingPeriodStarts:
    """UTC cutoffs aligned with Beijing calendar day boundaries."""
    beijing_today_start = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start = beijing_today_start.astimezone(timezone.utc).replace(tzinfo=None)
    week_ago = (beijing_today_start - timedelta(days=7)).astimezone(timezone.utc).replace(
        tzinfo=None
    )
    month_ago = (beijing_today_start - timedelta(days=30)).astimezone(timezone.utc).replace(
        tzinfo=None
    )
    return {
        "today_start": today_start,
        "week_ago": week_ago,
        "month_ago": month_ago,
        "beijing_today_start": beijing_today_start,
    }


def utc_date_to_beijing_key(utc_date: date | str, beijing_timezone: tzinfo) -> str:
    """Map a UTC calendar date to Beijing date string key."""
    if isinstance(utc_date, str):
        utc_date = datetime.strptime(utc_date, "%Y-%m-%d").date()
    utc_datetime = datetime.combine(utc_date, datetime.min.time())
    beijing_datetime = utc_datetime.replace(tzinfo=timezone.utc).astimezone(beijing_timezone)
    return str(beijing_datetime.date())
