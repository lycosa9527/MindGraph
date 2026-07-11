"""Tests for node-action debug logging helpers."""

from __future__ import annotations

from services.kitty.routing.node_action_debug import (
    build_diagram_snapshot_meta,
    clip_node_action_text,
    summarize_legacy_command,
)


def test_clip_node_action_text() -> None:
    """Long user text is clipped for log lines."""
    long_text = "a" * 200
    clipped = clip_node_action_text(long_text, limit=50)
    assert len(clipped) <= 50
    assert clipped.endswith("…")


def test_build_diagram_snapshot_meta() -> None:
    """Snapshot meta includes topic and branch labels for tuning logs."""
    meta = build_diagram_snapshot_meta(
        {
            "diagram_data": {
                "center": {"text": "茶叶"},
                "children": [{"text": "中国"}, {"text": "日本"}],
            },
        },
        diagram_type="mindmap",
    )
    assert meta["topic"] == "茶叶"
    assert meta["branch_count"] == 2
    assert meta["branches"] == ["中国", "日本"]
    assert meta["node_count"] == 0


def test_summarize_legacy_command() -> None:
    """Legacy command summary includes action and target."""
    text = summarize_legacy_command(
        {"action": "auto_complete_branch", "target": "中国", "confidence": 0.95},
    )
    assert "auto_complete_branch" in text
    assert "中国" in text
    assert "0.95" in text
