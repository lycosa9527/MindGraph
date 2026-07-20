"""Tests for Kitty LLMOps manifest and voice intent catalog."""

from __future__ import annotations

from services.kitty.http.llmops_manifest import build_kitty_llmops_manifest
from services.kitty.routing.intent_catalog import KITTY_INTENT_ROWS


def test_voice_intent_row_counts() -> None:
    """5 diagram + 19 UI + 1 flow = 25 named rows."""
    diagram = sum(1 for r in KITTY_INTENT_ROWS if r["kind"] == "diagram")
    ui = sum(1 for r in KITTY_INTENT_ROWS if r["kind"] == "ui")
    flow = sum(1 for r in KITTY_INTENT_ROWS if r["kind"] == "flow")
    assert diagram == 5
    assert ui == 19
    assert flow == 1


def test_llmops_manifest_shape() -> None:
    """Test llmops manifest shape."""
    m = build_kitty_llmops_manifest()
    assert m["version"]
    assert isinstance(m["modules"], list) and len(m["modules"]) >= 3
    assert "mermaid_kitty_hub" in m
    assert len(m["intents"]) == 25
    assert len(m["special_flows"]) == 3
    assert m["intent_counts"]["diagram_named"] == 5
    assert m["intent_counts"]["ui_named"] == 19
