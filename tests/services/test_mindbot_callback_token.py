"""Tests for MindBot public callback token generation."""

from __future__ import annotations

from services.mindbot.mindbot_callback_token import new_public_callback_token


def test_new_public_callback_token_shape() -> None:
    seen = set()
    for _ in range(20):
        tok = new_public_callback_token()
        assert 16 <= len(tok) <= 64
        assert "\n" not in tok
        assert "\r" not in tok
        assert tok not in seen
        seen.add(tok)
