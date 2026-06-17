"""Unit tests for MindBot token aggregation helpers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.mindbot.errors import MindbotErrorCode
from utils.auth.mindbot_token_stats import (
    MINDBOT_USAGE_SUCCESS_CODES,
    TokenPeriodTotals,
    add_service_period,
    add_token_period,
    empty_token_period,
    merge_mindbot_hourly_into_tokens_by_hour,
    merge_mindbot_tokens_into_top_user_rows,
    merge_org_token_stats,
)


def test_success_codes_match_mindbot_ok_and_accepted():
    """Test success codes match mindbot ok and accepted."""
    assert MindbotErrorCode.OK.value in MINDBOT_USAGE_SUCCESS_CODES
    assert MindbotErrorCode.ACCEPTED.value in MINDBOT_USAGE_SUCCESS_CODES


def test_add_token_period_sums_fields():
    """Test add token period sums fields."""
    base = {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
    extra: TokenPeriodTotals = {
        "input_tokens": 1,
        "output_tokens": 2,
        "total_tokens": 3,
        "request_count": 1,
    }
    merged = add_token_period(base, extra)
    assert merged == {"input_tokens": 11, "output_tokens": 22, "total_tokens": 33}


def test_add_service_period_includes_request_count():
    """Test add service period includes request count."""
    base = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "request_count": 2}
    extra = empty_token_period()
    extra["input_tokens"] = 5
    extra["output_tokens"] = 7
    extra["total_tokens"] = 12
    extra["request_count"] = 3
    merged = add_service_period(base, extra)
    assert merged["request_count"] == 5
    assert merged["total_tokens"] == 12


def test_merge_org_token_stats_adds_and_creates():
    """Test merge org token stats adds and creates."""
    base = {
        "School A": {
            "org_id": 1,
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "request_count": 2,
        },
    }
    extra = {
        "School A": {
            "org_id": 1,
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "request_count": 1,
        },
        "School B": {
            "org_id": 2,
            "input_tokens": 1,
            "output_tokens": 1,
            "total_tokens": 2,
            "request_count": 1,
        },
    }
    merged = merge_org_token_stats(base, extra)
    assert merged["School A"]["total_tokens"] == 165
    assert merged["School A"]["request_count"] == 3
    assert merged["School B"]["total_tokens"] == 2


def test_merge_mindbot_hourly_into_tokens_by_hour():
    """Test merge mindbot hourly into tokens by hour."""
    tokens_by_hour = {"2026-06-06 10:00:00": {"total": 1, "input": 0, "output": 1}}
    mindbot = {"2026-06-06 10:00:00": {"total": 5, "input": 2, "output": 3}}
    merge_mindbot_hourly_into_tokens_by_hour(tokens_by_hour, mindbot)
    assert tokens_by_hour["2026-06-06 10:00:00"]["total"] == 6
    assert tokens_by_hour["2026-06-06 10:00:00"]["input"] == 2


@pytest.mark.asyncio
async def test_merge_mindbot_tokens_into_top_user_rows_reorders_by_total():
    """Test merge mindbot tokens into top user rows reorders by total."""
    rows = [
        {"id": 1, "name": "A", "total_tokens": 100, "input_tokens": 0, "output_tokens": 0},
        {"id": 2, "name": "B", "total_tokens": 50, "input_tokens": 0, "output_tokens": 0},
    ]
    mindbot: dict[int, TokenPeriodTotals] = {
        2: {
            "input_tokens": 10,
            "output_tokens": 70,
            "total_tokens": 80,
            "request_count": 1,
        },
    }
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(first=lambda: None))
    merged = await merge_mindbot_tokens_into_top_user_rows(
        db,
        rows,
        mindbot,
        limit=10,
        include_io_tokens=True,
    )
    assert merged[0]["id"] == 2
    assert merged[0]["total_tokens"] == 130
    assert merged[0]["input_tokens"] == 10
    assert merged[1]["id"] == 1


@pytest.mark.asyncio
async def test_merge_mindbot_tokens_promotes_linked_user():
    """Test merge mindbot tokens promotes linked user."""
    rows = [{"id": 1, "name": "A", "total_tokens": 10}]
    mindbot: dict[int, TokenPeriodTotals] = {
        99: {
            "input_tokens": 1,
            "output_tokens": 499,
            "total_tokens": 500,
            "request_count": 1,
        },
    }
    user_row = MagicMock()
    user_row.id = 99
    user_row.phone = "13800000099"
    user_row.name = "Bot User"
    user_row.organization_name = "School A"
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(first=lambda: user_row))
    merged = await merge_mindbot_tokens_into_top_user_rows(
        db,
        rows,
        mindbot,
        limit=10,
        mask_phone=True,
        include_org_name=True,
    )
    assert len(merged) == 2
    assert merged[0]["id"] == 99
    assert merged[0]["total_tokens"] == 500
