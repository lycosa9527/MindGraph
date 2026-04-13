"""Tests for DingTalk inbound debug logging (env-gated)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.mindbot import dingtalk_inbound_log as dil


def test_logging_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINDBOT_LOG_CALLBACK_INBOUND", raising=False)
    monkeypatch.delenv("MINDBOT_LOG_CALLBACK_INBOUND_FULL", raising=False)
    assert dil.dingtalk_inbound_logging_enabled() is False


def test_full_mode_enables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_LOG_CALLBACK_INBOUND_FULL", "1")
    assert dil.dingtalk_inbound_logging_enabled() is True
    assert dil.dingtalk_inbound_full_logging() is True


def test_log_dingtalk_inbound_noop_when_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINDBOT_LOG_CALLBACK_INBOUND", raising=False)
    monkeypatch.delenv("MINDBOT_LOG_CALLBACK_INBOUND_FULL", raising=False)
    req = MagicMock()
    dil.log_dingtalk_inbound(req, b"{}", "t")
