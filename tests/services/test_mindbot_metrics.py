"""Tests for MindBot in-process metrics."""

from __future__ import annotations

from services.mindbot.errors import MindbotErrorCode
from services.mindbot.telemetry.metrics import MindbotMetrics


def test_record_from_headers_aggregates_by_org_and_robot() -> None:
    m = MindbotMetrics()
    m.record_from_headers(
        {
            "X-MindBot-Error-Code": MindbotErrorCode.OK.value,
            "X-MindBot-Organization-Id": "5",
            "X-MindBot-Robot-Code": "robot-a",
        },
    )
    snap = m.snapshot()
    assert snap["by_error_code"][MindbotErrorCode.OK.value] == 1
    assert snap["by_organization_id"][5][MindbotErrorCode.OK.value] == 1
    assert snap["by_robot_code"]["robot-a"][MindbotErrorCode.OK.value] == 1


def test_record_from_headers_without_org_still_counts_code() -> None:
    m = MindbotMetrics()
    m.record_from_headers({"X-MindBot-Error-Code": MindbotErrorCode.DIFY_FAILED.value})
    snap = m.snapshot()
    assert snap["by_error_code"][MindbotErrorCode.DIFY_FAILED.value] == 1
    assert snap["by_organization_id"] == {}
    assert snap["by_robot_code"] == {}


def test_record_from_headers_missing_code_uses_unknown_bucket() -> None:
    """Headers without X-MindBot-Error-Code must use MINDBOT_MISSING_CODE, not OK."""
    m = MindbotMetrics()
    m.record_from_headers({})
    snap = m.snapshot()
    # Must NOT be counted as MINDBOT_OK
    assert snap["by_error_code"].get(MindbotErrorCode.OK.value, 0) == 0
    # Must be counted under the missing-code sentinel
    assert snap["by_error_code"].get("MINDBOT_MISSING_CODE", 0) == 1


def test_record_from_headers_empty_code_string_uses_unknown_bucket() -> None:
    """An explicitly empty X-MindBot-Error-Code header must use MINDBOT_MISSING_CODE."""
    m = MindbotMetrics()
    m.record_from_headers({"X-MindBot-Error-Code": ""})
    snap = m.snapshot()
    assert snap["by_error_code"].get("MINDBOT_MISSING_CODE", 0) == 1


# ---------------------------------------------------------------------------
# MindbotErrorCode.retryable property
# ---------------------------------------------------------------------------


def test_retryable_true_for_transient_codes() -> None:
    """Transient error codes (Dify failures, outbound failures) must be retryable."""
    assert MindbotErrorCode.DIFY_FAILED.retryable is True
    assert MindbotErrorCode.SESSION_WEBHOOK_FAILED.retryable is True
    assert MindbotErrorCode.DINGTALK_TOKEN_FAILED.retryable is True
    assert MindbotErrorCode.DINGTALK_OPENAPI_REPLY_FAILED.retryable is True
    assert MindbotErrorCode.REDIS_UNAVAILABLE_FOR_DEDUP.retryable is True
    assert MindbotErrorCode.CIRCUIT_OPEN.retryable is True
    assert MindbotErrorCode.PIPELINE_INTERNAL_ERROR.retryable is True


def test_retryable_false_for_permanent_codes() -> None:
    """Permanent errors (bad signature, duplicate, rate limit, etc.) must not be retried."""
    assert MindbotErrorCode.OK.retryable is False
    assert MindbotErrorCode.INVALID_SIGNATURE.retryable is False
    assert MindbotErrorCode.DUPLICATE_MESSAGE.retryable is False
    assert MindbotErrorCode.RATE_LIMITED.retryable is False
    assert MindbotErrorCode.FEATURE_DISABLED.retryable is False
    assert MindbotErrorCode.EMPTY_USER_MESSAGE.retryable is False
    assert MindbotErrorCode.CONFIG_NOT_FOUND.retryable is False
    assert MindbotErrorCode.SESSION_WEBHOOK_INVALID_URL.retryable is False
