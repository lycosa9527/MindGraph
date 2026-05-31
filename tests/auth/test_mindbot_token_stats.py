"""Unit tests for MindBot token aggregation helpers."""

from utils.auth.mindbot_token_stats import (
    MINDBOT_USAGE_SUCCESS_CODES,
    add_service_period,
    add_token_period,
    empty_token_period,
    merge_org_token_stats,
)
from services.mindbot.errors import MindbotErrorCode


def test_success_codes_match_mindbot_ok_and_accepted():
    assert MindbotErrorCode.OK.value in MINDBOT_USAGE_SUCCESS_CODES
    assert MindbotErrorCode.ACCEPTED.value in MINDBOT_USAGE_SUCCESS_CODES


def test_add_token_period_sums_fields():
    base = {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
    extra = {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3, "request_count": 1}
    merged = add_token_period(base, extra)
    assert merged == {"input_tokens": 11, "output_tokens": 22, "total_tokens": 33}


def test_add_service_period_includes_request_count():
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
