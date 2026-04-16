"""Tests for outbound/text.py (is_group_conversation, _sanitize_webhook_snippet)."""

from __future__ import annotations

import pytest

from services.mindbot.outbound.text import _sanitize_webhook_snippet, is_group_conversation


# ---------------------------------------------------------------------------
# is_group_conversation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("conv_type", ["2", "group", "GROUP", " 2 "])
def test_is_group_conversation_truthy(conv_type: str) -> None:
    body = {"conversationType": conv_type}
    assert is_group_conversation(body) is True


@pytest.mark.parametrize("conv_type", ["1", "oto", "private", "0"])
def test_is_group_conversation_falsy_explicit(conv_type: str) -> None:
    body = {"conversationType": conv_type}
    assert is_group_conversation(body) is False


def test_is_group_conversation_missing_field() -> None:
    assert is_group_conversation({}) is False


def test_is_group_conversation_none_value() -> None:
    assert is_group_conversation({"conversationType": None}) is False


def test_is_group_conversation_uses_snake_case_fallback() -> None:
    assert is_group_conversation({"conversation_type": "2"}) is True


def test_is_group_conversation_camel_takes_precedence() -> None:
    body = {"conversationType": "2", "conversation_type": "1"}
    assert is_group_conversation(body) is True


# ---------------------------------------------------------------------------
# _sanitize_webhook_snippet
# ---------------------------------------------------------------------------


def test_sanitize_webhook_snippet_redacts_access_token() -> None:
    body = '{"accessToken": "sk-very-secret-token", "msg": "hello"}'
    result = _sanitize_webhook_snippet(body)
    assert "sk-very-secret-token" not in result
    assert '"accessToken"' in result
    assert "***" in result


def test_sanitize_webhook_snippet_redacts_token_field() -> None:
    body = '{"token": "abc123xyz"}'
    result = _sanitize_webhook_snippet(body)
    assert "abc123xyz" not in result


def test_sanitize_webhook_snippet_preserves_non_sensitive_fields() -> None:
    body = '{"status": "ok", "msg": "hello world"}'
    result = _sanitize_webhook_snippet(body)
    assert "ok" in result
    assert "hello world" in result


def test_sanitize_webhook_snippet_truncates_to_max_len() -> None:
    long_body = "x" * 1000
    result = _sanitize_webhook_snippet(long_body, max_len=100)
    assert len(result) <= 100


def test_sanitize_webhook_snippet_empty_input() -> None:
    assert _sanitize_webhook_snippet("") == ""


def test_sanitize_webhook_snippet_case_insensitive() -> None:
    body = '{"AccessToken": "secret-value-here"}'
    result = _sanitize_webhook_snippet(body)
    assert "secret-value-here" not in result
