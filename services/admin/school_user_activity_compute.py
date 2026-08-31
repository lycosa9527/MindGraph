"""Pure Beijing-calendar aggregations for school user-activity cards.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Sequence

from services.admin.school_user_activity_types import (
    ActivityBlock,
    BucketPoint,
    FrequencyBlock,
    HourPoint,
    LoginStamp,
    OrgUserStamp,
    SeriesPoint,
    TotalsBlock,
)

BEIJING_TIMEZONE = timezone(timedelta(hours=8))

LOGIN_COUNT_BUCKETS: tuple[tuple[str, int | None], ...] = (
    ("0", 0),
    ("1-2", 2),
    ("3-9", 9),
    ("10-29", 29),
    ("30+", None),
)
HIGH_FREQ_DAILY_MIN = 3.0
LOW_FREQ_MONTHLY_MAX = 3.0
_HOURS_IN_DAY = 24
_MONTHS_IN_YEAR = 12


def to_beijing(value: datetime) -> datetime:
    """Treat naive timestamps as UTC and convert to Beijing."""
    if value.tzinfo is None:
        aware = value.replace(tzinfo=timezone.utc)
    else:
        aware = value
    return aware.astimezone(BEIJING_TIMEZONE)


def year_bounds(year: int) -> tuple[datetime, datetime]:
    """Inclusive Beijing start and exclusive end for a calendar year."""
    start = datetime(year, 1, 1, tzinfo=BEIJING_TIMEZONE)
    end = datetime(year + 1, 1, 1, tzinfo=BEIJING_TIMEZONE)
    return start, end


def period_end(year: int, now_beijing: datetime) -> datetime:
    """Last instant included in averages for the selected year."""
    _start, year_end = year_bounds(year)
    if now_beijing.year < year:
        return _start
    if now_beijing.year > year:
        return year_end - timedelta(microseconds=1)
    return now_beijing


def min_activity_year(users: Sequence[OrgUserStamp], current_year: int) -> int:
    """Earliest org-user created year, or the current year when the school is empty."""
    if not users:
        return current_year
    first = min(to_beijing(row["created_at"]).year for row in users)
    return first


def _round_one(value: float) -> float:
    return round(value, 1)


def _mean(values: Sequence[int]) -> float:
    if not values:
        return 0.0
    return _round_one(sum(values) / len(values))


def _month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _quarter_key(year: int, month: int) -> str:
    quarter = ((month - 1) // 3) + 1
    return f"{year:04d}-Q{quarter}"


def _days_enrolled(created: date, year_start: date, period_last: date) -> int:
    start = max(created, year_start)
    end = period_last
    if start > end:
        return 0
    return max(1, (end - start).days + 1)


def _months_enrolled(created: date, year_start: date, period_last: date) -> int:
    start = max(created, year_start)
    if start > period_last:
        return 0
    return max(
        1,
        (period_last.year - start.year) * _MONTHS_IN_YEAR + (period_last.month - start.month) + 1,
    )


def _bucket_label(count: int) -> str:
    if count <= 0:
        return "0"
    if count <= 2:
        return "1-2"
    if count <= 9:
        return "3-9"
    if count <= 29:
        return "10-29"
    return "30+"


def build_totals(
    users: Sequence[OrgUserStamp],
    year: int,
    now_beijing: datetime,
) -> TotalsBlock:
    """Build 用户总量 series and headline counts."""
    year_start, year_end = year_bounds(year)
    created_beijing = [to_beijing(row["created_at"]) for row in users]
    year_new = [stamp for stamp in created_beijing if year_start <= stamp < year_end]
    baseline = sum(1 for stamp in created_beijing if stamp < year_start)
    last_month = _MONTHS_IN_YEAR
    if now_beijing.year == year:
        last_month = now_beijing.month

    year_new_series: list[SeriesPoint] = []
    cumulative_series: list[SeriesPoint] = []
    running = baseline
    for month in range(1, _MONTHS_IN_YEAR + 1):
        month_start = datetime(year, month, 1, tzinfo=BEIJING_TIMEZONE)
        if month == _MONTHS_IN_YEAR:
            month_end = year_end
        else:
            month_end = datetime(year, month + 1, 1, tzinfo=BEIJING_TIMEZONE)
        added = sum(1 for stamp in year_new if month_start <= stamp < month_end)
        if month <= last_month:
            running += added
        key = _month_key(year, month)
        year_new_series.append({"date": key, "value": added if month <= last_month else 0})
        cumulative_series.append({"date": key, "value": running if month <= last_month else 0})

    enrolled = len(users)
    return {
        "cumulative_registered": enrolled,
        "year_new_users": len(year_new),
        "churn_available": False,
        "enrolled_today": enrolled,
        "cumulative_series": cumulative_series,
        "year_new_series": year_new_series,
        "enrolled_series": list(cumulative_series),
    }


def build_activity(
    users: Sequence[OrgUserStamp],
    logins: Sequence[LoginStamp],
    year: int,
    now_beijing: datetime,
) -> ActivityBlock:
    """Build monthly / quarterly / daily active-user series and averages."""
    year_start, year_end = year_bounds(year)
    end = period_end(year, now_beijing)
    org_ids = {row["user_id"] for row in users}
    daily: dict[date, set[int]] = defaultdict(set)
    monthly: dict[str, set[int]] = defaultdict(set)
    quarterly: dict[str, set[int]] = defaultdict(set)

    for login in logins:
        if login["user_id"] not in org_ids:
            continue
        stamp = to_beijing(login["created_at"])
        if stamp < year_start or stamp >= year_end:
            continue
        daily[stamp.date()].add(login["user_id"])
        monthly[_month_key(stamp.year, stamp.month)].add(login["user_id"])
        quarterly[_quarter_key(stamp.year, stamp.month)].add(login["user_id"])

    daily_series: list[SeriesPoint] = []
    cursor = year_start.date()
    last_day = end.date()
    if last_day < cursor:
        last_day = cursor - timedelta(days=1)
    while cursor <= last_day:
        daily_series.append({"date": cursor.isoformat(), "value": len(daily[cursor])})
        cursor += timedelta(days=1)

    monthly_series: list[SeriesPoint] = []
    last_month = _MONTHS_IN_YEAR if now_beijing.year != year else now_beijing.month
    if now_beijing.year > year:
        last_month = _MONTHS_IN_YEAR
    if now_beijing.year < year:
        last_month = 0
    for month in range(1, _MONTHS_IN_YEAR + 1):
        key = _month_key(year, month)
        value = len(monthly[key]) if month <= last_month else 0
        monthly_series.append({"date": key, "value": value})

    quarterly_series: list[SeriesPoint] = []
    for quarter in range(1, 5):
        key = f"{year:04d}-Q{quarter}"
        first_month = (quarter - 1) * 3 + 1
        value = len(quarterly[key]) if first_month <= last_month else 0
        quarterly_series.append({"date": key, "value": value})

    elapsed_months = [point["value"] for point in monthly_series[: max(last_month, 0)]]
    return {
        "daily_active": daily_series,
        "monthly_active": monthly_series,
        "quarterly_active": quarterly_series,
        "avg_daily_active": _mean([point["value"] for point in daily_series]),
        "avg_monthly_active": _mean(elapsed_months),
    }


def build_frequency(
    users: Sequence[OrgUserStamp],
    logins: Sequence[LoginStamp],
    year: int,
    now_beijing: datetime,
) -> FrequencyBlock:
    """Build login-count histogram, high/low shares, and hour-of-day bars."""
    year_start, year_end = year_bounds(year)
    end = period_end(year, now_beijing)
    year_start_date = year_start.date()
    period_last = end.date()
    enrolled = [row for row in users if to_beijing(row["created_at"]).date() <= period_last]
    counts: dict[int, int] = {row["user_id"]: 0 for row in enrolled}
    hours = [0] * _HOURS_IN_DAY
    org_ids = {row["user_id"] for row in enrolled}

    for login in logins:
        user_id = login["user_id"]
        if user_id not in org_ids:
            continue
        stamp = to_beijing(login["created_at"])
        if stamp < year_start or stamp >= year_end:
            continue
        counts[user_id] = counts.get(user_id, 0) + 1
        hours[stamp.hour] += 1

    buckets = {label: 0 for label, _edge in LOGIN_COUNT_BUCKETS}
    for count in counts.values():
        buckets[_bucket_label(count)] += 1
    bucket_points: list[BucketPoint] = [
        {"label": label, "value": buckets[label]} for label, _edge in LOGIN_COUNT_BUCKETS
    ]

    created_by_id = {row["user_id"]: to_beijing(row["created_at"]).date() for row in enrolled}
    high_count = 0
    low_count = 0
    for user_id, login_count in counts.items():
        created = created_by_id[user_id]
        days = _days_enrolled(created, year_start_date, period_last)
        months = _months_enrolled(created, year_start_date, period_last)
        daily_avg = login_count / days if days else 0.0
        monthly_avg = login_count / months if months else 0.0
        if daily_avg >= HIGH_FREQ_DAILY_MIN:
            high_count += 1
        if months and monthly_avg <= LOW_FREQ_MONTHLY_MAX:
            low_count += 1

    roster = len(enrolled)
    share_high = _round_one((high_count / roster) * 100) if roster else 0.0
    share_low = _round_one((low_count / roster) * 100) if roster else 0.0
    hour_points: list[HourPoint] = [{"hour": hour, "value": hours[hour]} for hour in range(_HOURS_IN_DAY)]
    return {
        "login_count_buckets": bucket_points,
        "high_freq_count": high_count,
        "high_freq_share": share_high,
        "low_freq_count": low_count,
        "low_freq_share": share_low,
        "hour_of_day": hour_points,
    }
