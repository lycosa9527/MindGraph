"""Activity tracker records client_source on sessions and history."""

from __future__ import annotations

import pytest

from services.redis.redis_activity_tracker import RedisActivityTracker


@pytest.mark.asyncio
async def test_memory_record_activity_stores_client_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In-memory path keeps client_source on the session and history entry."""
    tracker = RedisActivityTracker()
    monkeypatch.setattr(tracker, "_use_redis", lambda: False)

    await tracker.record_activity(
        user_id=42,
        user_phone="13800000000",
        activity_type="diagram_generation",
        details={"diagram_type": "mind_map"},
        user_name="Ada",
        client_source="chrome-extension",
    )

    users = await tracker.get_active_users(hours=1)
    assert len(users) == 1
    assert users[0]["client_source"] == "chrome-extension"
    assert users[0]["client_source_label"] == "Chrome extension"

    activities = await tracker.get_recent_activities(limit=10)
    assert activities
    assert activities[0]["client_source"] == "chrome-extension"
    assert activities[0]["details"]["client_source"] == "chrome-extension"
    assert activities[0]["details"]["diagram_type"] == "mind_map"


@pytest.mark.asyncio
async def test_saved_brainstorm_activity_uses_the_current_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Older stored activity rows display as AI brainstorm."""
    tracker = RedisActivityTracker()
    monkeypatch.setattr(tracker, "_use_redis", lambda: False)
    assert "node_palette" not in tracker.ACTIVITY_TYPES

    await tracker.record_activity(
        user_id=7,
        user_phone="13800000001",
        activity_type="node_palette",
        details={},
        user_name="Ada",
    )

    users = await tracker.get_active_users(hours=1)
    assert users[0]["current_activity_label"] == "Using AI brainstorm"
    activities = await tracker.get_recent_activities(limit=5)
    assert activities[0]["activity_label"] == "Using AI brainstorm"
