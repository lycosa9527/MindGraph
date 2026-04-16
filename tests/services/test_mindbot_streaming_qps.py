"""Unit tests for DingTalk streaming card QPS helpers."""

from __future__ import annotations

from services.mindbot.platforms.dingtalk.cards.streaming_qps import (
    dingtalk_streaming_body_is_qps_throttle,
)


def test_qps_throttle_detection_new_api_codes() -> None:
    assert dingtalk_streaming_body_is_qps_throttle(
        {"code": "Forbidden.AccessDenied.QpsLimitForAppkeyAndApi", "message": "x"}
    )
    assert dingtalk_streaming_body_is_qps_throttle(
        {"code": "Forbidden.AccessDenied.QpsLimitForApi", "message": "x"}
    )


def test_qps_throttle_detection_legacy_codes() -> None:
    assert dingtalk_streaming_body_is_qps_throttle({"code": "90018", "message": ""})
    assert dingtalk_streaming_body_is_qps_throttle({"code": "", "message": "90002 error"})


def test_qps_throttle_detection_negative() -> None:
    assert not dingtalk_streaming_body_is_qps_throttle(None)
    assert not dingtalk_streaming_body_is_qps_throttle(
        {"code": "param.stream.contentEmpty", "message": "empty"},
    )
