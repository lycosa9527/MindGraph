"""Tests for canvas translate thinking coin billing tier."""

from __future__ import annotations

from models.requests.requests_canvas_translate import CANVAS_TRANSLATE_MODEL
from utils.auth.thinking_coin_config import CANVAS_ASSIST_REQUEST_TYPES


def test_canvas_translate_uses_canvas_assist_cost_tier() -> None:
    """Canvas translate bills against canvas_assist pricing."""
    assert "canvas_translate" in CANVAS_ASSIST_REQUEST_TYPES


def test_canvas_translate_uses_qwen38_flash() -> None:
    """Diagram label translate is pinned to DashScope qwen3.8-flash."""
    assert CANVAS_TRANSLATE_MODEL == "qwen3.8-flash"
