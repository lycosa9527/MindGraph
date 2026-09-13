"""Slide-remote Redis document and command queue."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from services.features.slides_remote.session_store import (
    SlideRemoteError,
    drain_commands,
    end_session,
    enqueue_command,
    get_session,
    idle_snapshot,
    normalize_command,
    public_snapshot,
    touch_session,
    upsert_session,
)


class FakeRedis:
    """In-memory stand-in for get/set/delete/rpush/lpop/ltrim/expire/publish."""

    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}
        self.published: list[tuple[str, str]] = []
        self.expires: list[tuple[str, int]] = []

    async def get(self, key: str) -> str | None:
        """Return a stored string or None."""
        return self.kv.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        """Write a string value and ignore TTL."""
        del ex
        self.kv[key] = value

    async def delete(self, *keys: str) -> None:
        """Drop keys from both maps."""
        for key in keys:
            self.kv.pop(key, None)
            self.lists.pop(key, None)

    async def rpush(self, key: str, value: str) -> None:
        """Append one list value."""
        self.lists.setdefault(key, []).append(value)

    async def lpop(self, key: str) -> str | None:
        """Pop the left-most list value."""
        rows = self.lists.get(key)
        if not rows:
            return None
        return rows.pop(0)

    async def ltrim(self, key: str, start: int, end: int) -> None:
        """Keep a Redis-style slice of the list."""
        rows = self.lists.get(key, [])
        if end == -1:
            self.lists[key] = rows[start:]
            return
        self.lists[key] = rows[start : end + 1]

    async def exists(self, key: str) -> int:
        """Return 1 when the string key is present."""
        return 1 if key in self.kv else 0

    async def expire(self, key: str, ttl: int) -> None:
        """Record TTL refresh (tests do not drop keys)."""
        self.expires.append((key, ttl))

    async def publish(self, channel: str, message: str) -> int:
        """Record a pub/sub wake (used when fanout shares this client)."""
        self.published.append((channel, message))
        return 1


def _fields(**overrides: Any) -> dict[str, Any]:
    body = {
        "diagram_id": "diag-1",
        "title": "中心",
        "slide_index": 1,
        "slide_count": 4,
        "traversal": "firstLevel",
        "autoplay": False,
        "can_prev": True,
        "can_next": True,
    }
    body.update(overrides)
    return body


def test_public_snapshot_idle_when_missing() -> None:
    """No Redis row looks idle to the watch."""
    view = public_snapshot(None)
    assert view["state"] == "idle"
    assert view["session_id"] == ""
    assert idle_snapshot()["can_next"] is False


def test_normalize_command_rejects_unknown() -> None:
    """Watch cannot invent actions."""
    with pytest.raises(SlideRemoteError) as exc:
        normalize_command({"action": "laser"})
    assert exc.value.code == "bad_action"


def test_normalize_command_requires_traversal_mode() -> None:
    """Traversal clicks must name firstLevel or deep."""
    with pytest.raises(SlideRemoteError) as exc:
        normalize_command({"action": "traversal"})
    assert exc.value.code == "bad_traversal"
    row = normalize_command({"action": "traversal", "mode": "deep"})
    assert row["mode"] == "deep"


def test_normalize_command_requires_start_diagram() -> None:
    """Start from the watch library must name a diagram."""
    with pytest.raises(SlideRemoteError) as exc:
        normalize_command({"action": "start"})
    assert exc.value.code == "bad_diagram"
    row = normalize_command({"action": "start", "diagram_id": "d9"})
    assert row["diagram_id"] == "d9"


@pytest.mark.asyncio
async def test_upsert_enqueue_drain_end() -> None:
    """Desktop publish, watch click, desktop drain, then end."""
    redis = FakeRedis()
    with patch(
        "services.features.slides_remote.session_store.get_async_redis",
        return_value=redis,
    ):
        created = await upsert_session(7, _fields())
        assert created["state"] == "live"
        assert created["session_id"]
        loaded = await get_session(7)
        assert loaded is not None
        view = public_snapshot(loaded)
        assert view["slide_index"] == 1
        assert view["slide_count"] == 4

        queued = await enqueue_command(7, {"action": "next"})
        assert queued["action"] == "next"
        items = await drain_commands(7)
        assert [row["action"] for row in items] == ["next"]
        assert await drain_commands(7) == []

        await end_session(7)
        assert await get_session(7) is None
        assert public_snapshot(await get_session(7))["state"] == "idle"


@pytest.mark.asyncio
async def test_enqueue_without_session_is_not_found() -> None:
    """Clicks except start are rejected until desktop is in 演讲模式."""
    redis = FakeRedis()
    with patch(
        "services.features.slides_remote.session_store.get_async_redis",
        return_value=redis,
    ):
        with pytest.raises(SlideRemoteError) as exc:
            await enqueue_command(3, {"action": "next"})
        assert exc.value.code == "not_found"


@pytest.mark.asyncio
async def test_enqueue_start_without_session() -> None:
    """Library Start can queue before desktop has opened 演讲模式."""
    redis = FakeRedis()
    with patch(
        "services.features.slides_remote.session_store.get_async_redis",
        return_value=redis,
    ):
        queued = await enqueue_command(3, {"action": "start", "diagram_id": "d9"})
        assert queued["action"] == "start"
        assert queued["diagram_id"] == "d9"
        items = await drain_commands(3)
        assert [row["diagram_id"] for row in items] == ["d9"]


@pytest.mark.asyncio
async def test_enqueue_publishes_command_pending_wake() -> None:
    """A queued click must wake desktop sockets."""
    redis = FakeRedis()
    with (
        patch(
            "services.features.slides_remote.session_store.get_async_redis",
            return_value=redis,
        ),
        patch(
            "services.features.slides_remote.session_store.publish_slides_command_pending",
            new=AsyncMock(),
        ) as wake,
    ):
        await enqueue_command(3, {"action": "start", "diagram_id": "d9"})
        wake.assert_awaited_once_with(3)


@pytest.mark.asyncio
async def test_upsert_publishes_snapshot_only_when_hud_changes() -> None:
    """TTL heartbeats must not wake the watch; HUD changes must."""
    redis = FakeRedis()
    with (
        patch(
            "services.features.slides_remote.session_store.get_async_redis",
            return_value=redis,
        ),
        patch(
            "services.features.slides_remote.session_store.publish_slides_snapshot_view",
            new=AsyncMock(),
        ) as snap,
    ):
        await upsert_session(2, _fields())
        assert snap.await_count == 1
        await upsert_session(2, _fields())
        assert snap.await_count == 1
        await upsert_session(2, _fields(slide_index=3))
        assert snap.await_count == 2


@pytest.mark.asyncio
async def test_upsert_refreshes_same_room() -> None:
    """A second publish keeps the session_id and bumps seq."""
    redis = FakeRedis()
    with patch(
        "services.features.slides_remote.session_store.get_async_redis",
        return_value=redis,
    ):
        first = await upsert_session(2, _fields())
        second = await upsert_session(2, _fields(slide_index=2, autoplay=True))
        assert second["session_id"] == first["session_id"]
        assert second["seq"] == first["seq"] + 1
        assert second["autoplay"] is True
        assert second["slide_index"] == 2


@pytest.mark.asyncio
async def test_touch_session_refreshes_ttl_when_live() -> None:
    """Desktop socket keep-alive is EXPIRE, not another PUT."""
    redis = FakeRedis()
    with patch(
        "services.features.slides_remote.session_store.get_async_redis",
        return_value=redis,
    ):
        await upsert_session(4, _fields())
        redis.expires.clear()
        assert await touch_session(4) is True
        keys = {key for key, _ttl in redis.expires}
        assert "slide_remote:user:4" in keys
        assert await touch_session(99) is False
