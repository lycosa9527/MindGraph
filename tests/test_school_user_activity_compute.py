"""Unit tests for school user-activity aggregations."""

from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from services.admin.school_user_activity_compute import (
    BEIJING_TIMEZONE,
    build_activity,
    build_frequency,
    build_totals,
    min_activity_year,
)
from services.admin.school_user_activity_stats import build_school_user_activity
from services.admin.school_user_activity_types import LoginStamp, OrgUserStamp
from tests.typing_helpers import as_type

_TZ = BEIJING_TIMEZONE


def _dt(year: int, month: int, day: int, hour: int = 8) -> datetime:
    return datetime(year, month, day, hour, tzinfo=_TZ)


def _user(user_id: int, created_at: datetime) -> OrgUserStamp:
    return {"user_id": user_id, "created_at": created_at}


def _login(user_id: int, created_at: datetime) -> LoginStamp:
    return {"user_id": user_id, "created_at": created_at}


def test_min_year_empty_school_uses_current():
    """Empty org falls back to the current Beijing year."""
    assert min_activity_year([], 2026) == 2026


def test_year_new_and_cumulative_series():
    """Year-new bars and cumulative include the prior-year baseline."""
    users = [
        _user(1, _dt(2025, 6, 1)),
        _user(2, _dt(2026, 1, 10)),
        _user(3, _dt(2026, 3, 5)),
    ]
    now = _dt(2026, 9, 1, 12)
    totals = build_totals(users, 2026, now)
    assert totals["cumulative_registered"] == 3
    assert totals["enrolled_today"] == 3
    assert totals["year_new_users"] == 2
    assert totals["churn_available"] is False
    assert totals["year_new_series"][0]["value"] == 1
    assert totals["year_new_series"][2]["value"] == 1
    assert totals["cumulative_series"][0]["value"] == 2
    assert totals["cumulative_series"][8]["value"] == 3
    assert totals["cumulative_series"][11]["value"] == 0
    assert totals["year_new_series"][11]["value"] == 0


def test_daily_monthly_quarterly_active_include_zero_days():
    """DAU mean includes zero days; monthly/quarterly use distinct users."""
    users = [
        _user(1, _dt(2026, 1, 1)),
        _user(2, _dt(2026, 1, 1)),
    ]
    logins = [
        _login(1, _dt(2026, 1, 2, 9)),
        _login(1, _dt(2026, 1, 2, 18)),
        _login(2, _dt(2026, 4, 1, 10)),
    ]
    now = _dt(2026, 1, 3, 12)
    activity = build_activity(users, logins, 2026, now)
    assert activity["daily_active"][0]["date"] == "2026-01-01"
    assert activity["daily_active"][0]["value"] == 0
    assert activity["daily_active"][1]["value"] == 1
    assert activity["monthly_active"][0]["value"] == 1
    assert activity["monthly_active"][3]["value"] == 0
    assert activity["quarterly_active"][0]["value"] == 1
    assert activity["avg_daily_active"] == 0.3


def test_frequency_thresholds_use_enrollment_days():
    """High-freq uses enrolled days; low-freq uses enrolled months."""
    users = [
        _user(1, _dt(2026, 1, 1)),
        _user(2, _dt(2026, 1, 1)),
    ]
    logins = [_login(1, _dt(2026, 1, 1, hour)) for hour in range(9)]
    now = _dt(2026, 1, 1, 23)
    frequency = build_frequency(users, logins, 2026, now)
    assert frequency["high_freq_count"] == 1
    assert frequency["low_freq_count"] == 1
    bucket_zero = next(item for item in frequency["login_count_buckets"] if item["label"] == "0")
    bucket_high = next(item for item in frequency["login_count_buckets"] if item["label"] == "3-9")
    assert bucket_zero["value"] == 1
    assert bucket_high["value"] == 1
    assert frequency["hour_of_day"][0]["value"] == 1
    assert frequency["hour_of_day"][8]["value"] == 1


@pytest.mark.asyncio
async def test_build_rejects_future_and_below_min_year(monkeypatch: pytest.MonkeyPatch) -> None:
    """Year validation does not need a live organization row."""

    async def _users(_db: object, _org_id: int) -> list[OrgUserStamp]:
        return [_user(1, _dt(2025, 6, 1))]

    monkeypatch.setattr(
        "services.admin.school_user_activity_stats.load_org_users",
        _users,
    )
    monkeypatch.setattr(
        "services.admin.school_user_activity_stats.beijing_now",
        lambda: _dt(2026, 9, 1, 12),
    )
    db = as_type(object(), AsyncSession)
    with pytest.raises(ValueError, match="invalid_year"):
        await build_school_user_activity(db, 7, 4099)
    with pytest.raises(ValueError, match="year_out_of_range"):
        await build_school_user_activity(db, 7, 2024)
