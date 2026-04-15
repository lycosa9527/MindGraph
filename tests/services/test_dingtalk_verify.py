"""Tests for DingTalk receive-message-1 HMAC verification."""

from __future__ import annotations

from services.mindbot.platforms.dingtalk.auth.verify import (
    compute_sign,
    extract_dingtalk_robot_auth_headers,
    verify_dingtalk_sign,
)


def test_compute_and_verify_roundtrip() -> None:
    secret = "test-app-secret"
    ts_ms = "1730000000000"
    sign = compute_sign(ts_ms, secret)
    assert verify_dingtalk_sign(ts_ms, sign, secret, now_ts=1730000000.0)


def test_verify_rejects_bad_sign() -> None:
    assert not verify_dingtalk_sign(
        "1730000000000",
        "not-the-signature",
        "test-app-secret",
        now_ts=1730000000.0,
    )


def test_extract_dingtalk_robot_auth_headers_strips() -> None:
    ts, sg = extract_dingtalk_robot_auth_headers(
        {"timestamp": "  1730000000000  ", "sign": "  abc==  "},
    )
    assert ts == "1730000000000"
    assert sg == "abc=="


def test_extract_empty_becomes_none() -> None:
    ts, sg = extract_dingtalk_robot_auth_headers({"timestamp": "   ", "sign": ""})
    assert ts is None
    assert sg is None
