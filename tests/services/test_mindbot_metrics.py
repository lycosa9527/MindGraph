"""Tests for MindBot in-process metrics."""

from __future__ import annotations

from services.mindbot.mindbot_errors import MindbotErrorCode
from services.mindbot.mindbot_metrics import MindbotMetrics


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
