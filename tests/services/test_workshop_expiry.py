"""Unit tests for workshop session expiry (Beijing calendar day)."""

from datetime import datetime, timezone

import pytest

from services.workshop.workshop_expiry import (
    compute_workshop_expires_at,
    duration_allowed_for_visibility,
    end_of_calendar_day_beijing_utc,
    DURATION_1H,
    DURATION_TODAY,
    DURATION_2D,
)


def test_duration_allowed_organization():
    assert duration_allowed_for_visibility("organization", DURATION_1H) is True
    assert duration_allowed_for_visibility("organization", DURATION_TODAY) is True
    assert duration_allowed_for_visibility("organization", DURATION_2D) is True


def test_duration_allowed_network_no_1h():
    assert duration_allowed_for_visibility("network", DURATION_1H) is False
    assert duration_allowed_for_visibility("network", DURATION_TODAY) is True
    assert duration_allowed_for_visibility("network", DURATION_2D) is True


def test_one_hour_from_utc_naive():
    start = datetime(2025, 3, 15, 10, 0, 0)
    exp = compute_workshop_expires_at(start, DURATION_1H)
    assert exp == datetime(2025, 3, 15, 11, 0, 0)


def test_end_of_day_beijing_same_calendar_day():
    start = datetime(2025, 3, 15, 10, 0, 0)
    end_direct = end_of_calendar_day_beijing_utc(start)
    exp = compute_workshop_expires_at(start, DURATION_TODAY)
    assert exp == end_direct.replace(tzinfo=None)
    assert end_direct > start.replace(tzinfo=timezone.utc)


def test_two_days_duration():
    start = datetime(2025, 3, 15, 10, 0, 0)
    exp = compute_workshop_expires_at(start, DURATION_2D)
    assert exp == datetime(2025, 3, 17, 10, 0, 0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
