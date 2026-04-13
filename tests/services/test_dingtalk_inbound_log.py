"""Tests for DingTalk inbound debug logging (env-gated)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.mindbot import dingtalk_inbound_log as dil


def test_logging_enabled_by_default_when_debug_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINDBOT_LOG_CALLBACK_INBOUND", raising=False)
    monkeypatch.delenv("MINDBOT_LOG_CALLBACK_INBOUND_FULL", raising=False)
    monkeypatch.delenv("MINDBOT_LOG_CALLBACK_DEBUG", raising=False)
    assert dil.dingtalk_inbound_logging_enabled() is True
    assert dil.dingtalk_inbound_full_logging() is True


def test_full_mode_enables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_LOG_CALLBACK_INBOUND_FULL", "1")
    assert dil.dingtalk_inbound_logging_enabled() is True
    assert dil.dingtalk_inbound_full_logging() is True


def test_debug_enables_full_inbound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINDBOT_LOG_CALLBACK_INBOUND", raising=False)
    monkeypatch.delenv("MINDBOT_LOG_CALLBACK_INBOUND_FULL", raising=False)
    monkeypatch.setenv("MINDBOT_LOG_CALLBACK_DEBUG", "1")
    assert dil.dingtalk_inbound_logging_enabled() is True
    assert dil.dingtalk_inbound_full_logging() is True


def test_log_dingtalk_inbound_noop_when_all_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINDBOT_LOG_CALLBACK_INBOUND", raising=False)
    monkeypatch.delenv("MINDBOT_LOG_CALLBACK_INBOUND_FULL", raising=False)
    monkeypatch.setenv("MINDBOT_LOG_CALLBACK_DEBUG", "0")
    req = MagicMock()
    dil.log_dingtalk_inbound(req, b"{}", "t")


def test_log_full_includes_parsed_json(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("MINDBOT_LOG_CALLBACK_INBOUND_FULL", "1")
    import logging

    caplog.set_level(logging.INFO)
    req = MagicMock()
    req.method = "POST"
    req.url.path = "/api/mindbot/dingtalk/callback"
    req.url.query = ""
    req.client = MagicMock()
    req.client.host = "127.0.0.1"
    req.headers = {"host": "a", "timestamp": "1", "sign": "x"}
    raw = b'{"robotCode":"r1"}'
    dil.log_dingtalk_inbound(req, raw, "shared", parsed_body={"robotCode": "r1"})
    assert "dingtalk_inbound_full" in caplog.text
    assert "body_parsed_json" in caplog.text
    assert "r1" in caplog.text


def test_debug_failure_logging_enabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINDBOT_LOG_CALLBACK_DEBUG", raising=False)
    assert dil.debug_callback_failure_logging_enabled() is True


def test_debug_failure_logging_explicit_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_LOG_CALLBACK_DEBUG", "0")
    assert dil.debug_callback_failure_logging_enabled() is False


def test_log_callback_failure_details_noop_when_debug_off(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("MINDBOT_LOG_CALLBACK_DEBUG", "0")
    import logging

    caplog.set_level(logging.INFO)
    dil.log_dingtalk_callback_failure_details(
        route_label="x",
        headers={"a": "b"},
        raw_body=b"{}",
        parsed_body={},
        reason="r",
    )
    assert "callback_debug_failure" not in caplog.text


def test_log_callback_failure_details_when_debug_on(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("MINDBOT_LOG_CALLBACK_DEBUG", "1")
    import logging

    caplog.set_level(logging.INFO)
    dil.log_dingtalk_callback_failure_details(
        route_label="shared",
        headers={"host": "example.com"},
        raw_body=b'{"robotCode":"r1"}',
        parsed_body={"robotCode": "r1"},
        reason="config_not_found",
        extra={"attempted_robot_code": "r1"},
    )
    assert "callback_debug_failure" in caplog.text
    assert "config_not_found" in caplog.text
    assert "body_parsed_json" in caplog.text or "body_raw" in caplog.text
