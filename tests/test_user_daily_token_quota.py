"""Tests for per-user daily token cap helpers."""

from __future__ import annotations

import pytest

from services.infrastructure.http.error_handler import UserDailyTokenCapExceededError
from utils.auth import user_daily_token_config as quota_config_mod
from utils.auth import user_daily_token_quota as quota_mod
from utils.auth.token_stats_queries import BEIJING_TIMEZONE, beijing_date_key
from utils.auth.user_daily_token_quota import (
    assert_user_daily_token_budget,
    daily_token_cap,
    daily_token_limit_message,
    daily_token_quota_fields,
    record_user_daily_tokens,
)


def test_daily_token_cap_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default cap is 1M when env unset."""
    monkeypatch.delenv("USER_DAILY_TOKEN_CAP", raising=False)
    assert daily_token_cap() == quota_config_mod.DEFAULT_USER_DAILY_TOKEN_CAP


def test_daily_token_cap_zero_disables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zero cap disables enforcement."""
    monkeypatch.setenv("USER_DAILY_TOKEN_CAP", "0")
    assert daily_token_cap() == 0


def test_beijing_date_key_format() -> None:
    """Beijing date key is YYYYMMDD."""
    from datetime import datetime

    dt = datetime(2026, 6, 19, 15, 30, tzinfo=BEIJING_TIMEZONE)
    assert beijing_date_key(dt) == "20260619"


def test_daily_token_quota_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quota fields compute remaining correctly."""
    monkeypatch.setenv("USER_DAILY_TOKEN_CAP", "1000000")
    fields = daily_token_quota_fields(250_000)
    assert fields["token_daily_cap"] == 1_000_000
    assert fields["token_used_today"] == 250_000
    assert fields["token_remaining_today"] == 750_000


def test_daily_token_quota_fields_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disabled cap reports zero cap and remaining."""
    monkeypatch.setenv("USER_DAILY_TOKEN_CAP", "0")
    fields = daily_token_quota_fields(99)
    assert fields["token_daily_cap"] == 0
    assert fields["token_remaining_today"] == 0


@pytest.mark.asyncio
async def test_assert_skips_anonymous_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """Anonymous calls are not capped."""
    monkeypatch.setenv("USER_DAILY_TOKEN_CAP", "100")

    async def fail_if_called(_user_id: int) -> int:
        raise AssertionError("should not query redis for anonymous user")

    monkeypatch.setattr(quota_mod, "get_daily_usage", fail_if_called)
    await assert_user_daily_token_budget(None)


@pytest.mark.asyncio
async def test_assert_raises_when_over_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exceeded budget raises UserDailyTokenCapExceededError."""
    monkeypatch.setenv("USER_DAILY_TOKEN_CAP", "1000")

    async def fake_usage(_user_id: int) -> int:
        return 1000

    monkeypatch.setattr(quota_mod, "get_daily_usage", fake_usage)

    with pytest.raises(UserDailyTokenCapExceededError) as exc_info:
        await assert_user_daily_token_budget(42, estimated_tokens=1, lang="en")

    assert exc_info.value.cap == 1000
    assert exc_info.value.used == 1000
    assert exc_info.value.user_message == daily_token_limit_message("en", 1000)


@pytest.mark.asyncio
async def test_assert_allows_under_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Usage below cap passes."""
    monkeypatch.setenv("USER_DAILY_TOKEN_CAP", "1000")

    async def fake_usage(_user_id: int) -> int:
        return 500

    monkeypatch.setattr(quota_mod, "get_daily_usage", fake_usage)
    await assert_user_daily_token_budget(42, estimated_tokens=400)


@pytest.mark.asyncio
async def test_record_skips_when_cap_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """No Redis write when cap disabled."""
    monkeypatch.setenv("USER_DAILY_TOKEN_CAP", "0")

    async def fail_if_called(_user_id: int, _tokens: int) -> int:
        raise AssertionError("should not increment when cap disabled")

    from services.redis.cache import redis_user_daily_token

    monkeypatch.setattr(redis_user_daily_token, "add_daily_usage", fail_if_called)
    await record_user_daily_tokens(7, 500)
