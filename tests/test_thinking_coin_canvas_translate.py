"""Tests for canvas translate thinking coin billing tier."""

from __future__ import annotations

from utils.auth.thinking_coin_config import CANVAS_ASSIST_REQUEST_TYPES


def test_canvas_translate_uses_canvas_assist_cost_tier() -> None:
    """Canvas translate bills against canvas_assist pricing."""
    assert "canvas_translate" in CANVAS_ASSIST_REQUEST_TYPES
