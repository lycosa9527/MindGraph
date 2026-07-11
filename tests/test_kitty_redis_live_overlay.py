"""Tests for Redis live_spec overlay into Kitty voice sessions."""

from __future__ import annotations

from services.kitty.infra.redis.kitty_session_redis import apply_redis_live_to_voice_session


def test_apply_redis_live_timestamp_lww() -> None:
    """Newer Redis live replaces diagram_data."""
    session: dict = {
        "_kitty_redis_seen_ts": 10,
        "context": {
            "diagram_data": {"nodes": [{"id": "old", "text": "A"}]},
            "interaction_language": "zh",
            "one_sentence_phase": "edit",
        },
    }
    live = {
        "updated_at": 20,
        "diagram_data": {"nodes": [{"id": "branch-r-1-0", "text": "品牌"}]},
        "selected_nodes": ["branch-r-1-0"],
        "diagram_type": "mindmap",
    }
    assert apply_redis_live_to_voice_session(session, live) is True
    assert session["context"]["diagram_data"]["nodes"][0]["id"] == "branch-r-1-0"
    assert session["context"]["interaction_language"] == "zh"
    assert session["context"]["one_sentence_phase"] == "edit"
    assert session["_kitty_redis_seen_ts"] == 20


def test_apply_redis_live_skips_stale_when_ws_has_nodes() -> None:
    """Stale Redis must not overwrite a newer WS flush that already has nodes."""
    session: dict = {
        "_kitty_redis_seen_ts": 30,
        "context": {
            "diagram_data": {"nodes": [{"id": "branch-r-1-1", "text": "使用场景"}]},
            "interaction_language": "zh",
        },
    }
    live = {
        "updated_at": 20,
        "diagram_data": {"nodes": [{"id": "branch-r-1-0", "text": "品牌"}]},
    }
    assert apply_redis_live_to_voice_session(session, live, prefer_live_diagram=True) is False
    assert session["context"]["diagram_data"]["nodes"][0]["id"] == "branch-r-1-1"


def test_prefer_live_heals_children_only_ws() -> None:
    """Route entry heals children-only WS from Redis canonical nodes."""
    session: dict = {
        "_kitty_redis_seen_ts": 50,
        "context": {
            "diagram_data": {"children": [{"text": "品牌"}]},
            "interaction_language": "zh",
        },
    }
    live = {
        "updated_at": 40,
        "diagram_data": {
            "nodes": [{"id": "branch-r-1-0", "text": "品牌"}],
            "connections": [{"source": "topic", "target": "branch-r-1-0"}],
        },
    }
    assert apply_redis_live_to_voice_session(session, live, prefer_live_diagram=True) is True
    assert session["context"]["diagram_data"]["nodes"][0]["id"] == "branch-r-1-0"
    assert session["context"]["interaction_language"] == "zh"
