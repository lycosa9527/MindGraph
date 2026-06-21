"""Beijing calendar helpers for thinking coins."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from utils.auth.token_stats_queries import BEIJING_TIMEZONE


def beijing_date_today() -> date:
    """Today's date in Beijing timezone."""
    return datetime.now(BEIJING_TIMEZONE).date()


def beijing_day_utc_bounds() -> tuple[datetime, datetime]:
    """Inclusive start and exclusive end of the current Beijing calendar day in UTC."""
    today = beijing_date_today()
    start_local = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=BEIJING_TIMEZONE)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def beijing_month_utc_bounds() -> tuple[datetime, datetime]:
    """Inclusive start and exclusive end of the current Beijing calendar month in UTC."""
    today = beijing_date_today()
    start_local = datetime(today.year, today.month, 1, 0, 0, 0, tzinfo=BEIJING_TIMEZONE)
    if today.month == 12:
        end_local = datetime(today.year + 1, 1, 1, 0, 0, 0, tzinfo=BEIJING_TIMEZONE)
    else:
        end_local = datetime(today.year, today.month + 1, 1, 0, 0, 0, tzinfo=BEIJING_TIMEZONE)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)
