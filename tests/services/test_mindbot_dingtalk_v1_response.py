"""Tests for DingTalk v1 JSON success semantics."""

from __future__ import annotations

from services.mindbot.platforms.dingtalk.api.response import (
    dingtalk_v1_body_log_snippet,
    dingtalk_v1_response_ok,
)


def test_success_explicit_true() -> None:
    assert dingtalk_v1_response_ok({"success": True, "result": {}}) is True


def test_success_empty_code() -> None:
    assert dingtalk_v1_response_ok({"code": "", "result": {"x": 1}}) is True


def test_failure_success_false() -> None:
    assert dingtalk_v1_response_ok({"success": False}) is False


def test_failure_nonzero_errcode() -> None:
    assert dingtalk_v1_response_ok({"errcode": 40014}) is False


def test_failure_nonempty_code_string() -> None:
    assert dingtalk_v1_response_ok({"code": "InvalidParameter"}) is False


def test_success_code_string_zero() -> None:
    assert dingtalk_v1_response_ok({"code": "0", "result": {"x": 1}}) is True


def test_failure_nested_error_code() -> None:
    assert dingtalk_v1_response_ok({"error": {"code": "x", "message": "m"}}) is False


def test_log_snippet_truncates() -> None:
    long_body = {"a": "x" * 500}
    s = dingtalk_v1_body_log_snippet(long_body, max_len=50)
    assert len(s) <= 54
    assert s.endswith("...")
