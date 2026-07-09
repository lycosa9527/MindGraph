"""Tests for unsupported diagram type detection and fallback acks."""

from __future__ import annotations

from services.kitty.ack.ack_library import render_unsupported_diagram_ack
from services.kitty.infra.bootstrap.kitty_unsupported_diagram_types import (
    resolve_unsupported_diagram_type,
    unsupported_match_from_unknown_slug,
)


def test_resolve_fishbone_from_chinese_text() -> None:
    """Fishbone mention in Chinese maps to mind map alternative."""
    match = resolve_unsupported_diagram_type(text="帮我画一张鱼骨图")
    assert match is not None
    assert match["entry_id"] == "fishbone"
    assert "鱼骨" in match["requested_type"]
    assert "思维导图" in match["alternative_label"]


def test_resolve_fishbone_from_english_slug() -> None:
    """Raw fishbone slug resolves without user sentence."""
    match = resolve_unsupported_diagram_type(raw_slug="fishbone", lang="en")
    assert match is not None
    assert "fishbone" in match["requested_type"].lower()
    assert "mind map" in match["alternative_label"].lower()


def test_resolve_ignores_unrelated_chat() -> None:
    """Casual chat without diagram intent does not trigger unsupported fallback."""
    assert resolve_unsupported_diagram_type(text="你好") is None


def test_render_unsupported_diagram_ack_zh() -> None:
    """Template mentions in-development and alternative."""
    match = resolve_unsupported_diagram_type(text="画鱼骨图")
    assert match is not None
    text = render_unsupported_diagram_ack(match, lang="zh")
    assert "开发" in text
    assert "思维导图" in text


def test_render_desktop_unsupported_ack() -> None:
    """Desktop-open variant names computer context."""
    match = resolve_unsupported_diagram_type(raw_slug="鱼骨图", lang="zh")
    assert match is not None
    text = render_unsupported_diagram_ack(match, lang="zh", desktop_open=True)
    assert "电脑" in text
    assert "鱼骨" in text


def test_unknown_slug_fallback_slots() -> None:
    """Unknown slug still yields mind map suggestion."""
    match = unsupported_match_from_unknown_slug("kpi_dashboard", lang="en")
    assert match["entry_id"] == "unknown"
    text = render_unsupported_diagram_ack(match, lang="en")
    assert "mind map" in text.lower()
