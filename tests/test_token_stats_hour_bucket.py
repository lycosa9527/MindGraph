"""Hour bucket helpers for admin token trend queries."""

from __future__ import annotations

from datetime import datetime

from models.domain.token_usage import TokenUsage
from utils.auth.token_stats_queries import (
    BEIJING_TIMEZONE,
    utc_hour_bucket,
    utc_naive_hour_to_beijing_key,
)


def test_utc_naive_hour_to_beijing_key_midnight_utc() -> None:
    """Test utc naive hour to beijing key midnight utc."""
    utc_hour = datetime(2026, 6, 6, 16, 0, 0)
    assert utc_naive_hour_to_beijing_key(utc_hour, BEIJING_TIMEZONE) == "2026-06-07 00:00:00"


def test_utc_naive_hour_to_beijing_key_from_string() -> None:
    """Test utc naive hour to beijing key from string."""
    assert utc_naive_hour_to_beijing_key("2026-06-06 08:00:00", BEIJING_TIMEZONE) == "2026-06-06 16:00:00"


def test_utc_hour_bucket_uses_date_trunc() -> None:
    """Test utc hour bucket uses date trunc."""
    bucket = utc_hour_bucket(TokenUsage.created_at)
    compiled = str(bucket)
    assert "date_trunc" in compiled.lower() or "trunc" in compiled.lower()
