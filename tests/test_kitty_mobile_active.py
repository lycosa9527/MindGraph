"""Tests for user-level Kitty mobile_active Redis signal and desktop poll gate."""

from __future__ import annotations

import json
import time
from types import SimpleNamespace
from typing import Any, Dict, Optional, cast
from unittest.mock import AsyncMock, patch

import pytest

from models.domain.auth import User
from services.kitty.http.handlers import (
    kitty_rest_desktop_action_enqueue,
    kitty_rest_desktop_action_pop,
    kitty_rest_desktop_pairing,
    kitty_rest_mobile_active_get,
)
from services.kitty.infra.desktop import (
    kitty_desktop_action_queue as queue,
)
from services.kitty.infra.desktop import (
    kitty_desktop_wake_fanout,
    kitty_mobile_active,
)
from services.kitty.infra.desktop.kitty_desktop_wake_fanout import build_kitty_desktop_wake_payload
from services.kitty.infra.redis import kitty_session_redis
from services.kitty.infra.redis.kitty_redis_keys import kitty_mobile_active_key, kitty_sessionmeta_key


def _kitty_user(user_id: int) -> User:
    """Kitty user."""
    return cast(User, SimpleNamespace(id=user_id))


class _FakeRedis:
    """_FakeRedis helper."""

    def __init__(self) -> None:
        """init  ."""
        self.data: Dict[str, str] = {}

    async def get(self, key: str) -> Optional[str]:
        """Get."""
        return self.data.get(key)

    async def set(self, key: str, val: str, ex: int | None = None) -> bool:
        """Set."""
        del ex
        self.data[key] = val
        return True

    async def delete(self, *keys: str) -> int:
        """Delete."""
        removed = 0
        for key in keys:
            if key in self.data:
                del self.data[key]
                removed += 1
        return removed

    async def publish(self, channel: str, message: str) -> int:
        """Publish."""
        del channel, message
        return 1

    def pipeline(self, transaction: bool = False) -> "_FakePipeline":
        """Pipeline."""
        return _FakePipeline(self, transaction=transaction)


class _FakePipeline:
    """_FakePipeline helper."""

    def __init__(self, redis: _FakeRedis, transaction: bool = False) -> None:
        """init  ."""
        self._redis = redis
        self._transaction = transaction
        self._ops: list[tuple[Any, ...]] = []
        self._watched: set[str] = set()
        self._in_multi = False

    async def watch(self, key: str) -> None:
        """Watch."""
        self._watched.add(key)

    async def get(self, key: str) -> Optional[str]:
        """Get."""
        return self._redis.data.get(key)

    def multi(self) -> None:
        """Multi."""
        self._in_multi = True

    def set(self, key: str, val: str, ex: int | None = None) -> None:
        """Set."""
        del ex
        self._ops.append(("set", key, val))

    def delete(self, *keys: str) -> None:
        """Delete."""
        self._ops.append(("delete", keys))

    async def execute(self) -> list[bool]:
        """Execute."""
        if self._transaction and not self._in_multi:
            return []
        count = 0
        for op in self._ops:
            if op[0] == "set":
                self._redis.data[op[1]] = op[2]
                count += 1
            elif op[0] == "delete":
                for key in op[1]:
                    self._redis.data.pop(key, None)
                count += 1
        self._ops = []
        self._in_multi = False
        self._watched = set()
        return [True] * count if count else [True]

    async def __aenter__(self) -> "_FakePipeline":
        """aenter  ."""
        return self

    async def __aexit__(self, *_args: Any) -> None:
        """aexit  ."""
        return None


def _patch_kitty_redis(monkeypatch: pytest.MonkeyPatch, fake: _FakeRedis) -> None:
    """Patch kitty redis."""
    monkeypatch.setattr(kitty_mobile_active, "get_async_redis", lambda: fake)
    monkeypatch.setattr(kitty_desktop_wake_fanout, "get_async_redis", lambda: fake)


@pytest.mark.asyncio
async def test_mark_and_read_mobile_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test mark and read mobile active."""
    fake = _FakeRedis()
    _patch_kitty_redis(monkeypatch, fake)

    await kitty_mobile_active.mark_kitty_mobile_active(42, "scope-a")
    out = await kitty_mobile_active.read_kitty_mobile_active(42)

    assert out["active"] is True
    assert out["scopes"] == ["scope-a"]
    assert out["primary_scope"] == "scope-a"


@pytest.mark.asyncio
async def test_clear_mobile_scope_deletes_key_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test clear mobile scope deletes key when empty."""
    fake = _FakeRedis()
    _patch_kitty_redis(monkeypatch, fake)

    await kitty_mobile_active.mark_kitty_mobile_active(7, "scope-x")
    await kitty_mobile_active.clear_kitty_mobile_scope(7, "scope-x")
    out = await kitty_mobile_active.read_kitty_mobile_active(7)

    assert out["active"] is False
    assert out["scopes"] == []
    assert kitty_mobile_active_key(7) not in fake.data


@pytest.mark.asyncio
async def test_clear_one_scope_keeps_others(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test clear one scope keeps others."""
    fake = _FakeRedis()
    _patch_kitty_redis(monkeypatch, fake)

    await kitty_mobile_active.mark_kitty_mobile_active(9, "scope-1")
    await kitty_mobile_active.mark_kitty_mobile_active(9, "scope-2")
    await kitty_mobile_active.clear_kitty_mobile_scope(9, "scope-1")
    out = await kitty_mobile_active.read_kitty_mobile_active(9)

    assert out["active"] is True
    assert out["scopes"] == ["scope-2"]
    assert out["primary_scope"] == "scope-2"


@pytest.mark.asyncio
async def test_upsert_desktop_start_clears_preserved_mobile_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test upsert desktop start clears preserved mobile lane."""
    fake = _FakeRedis()
    scope = "lib-diagram-uuid"
    meta_key = kitty_sessionmeta_key(scope)
    fake.data[meta_key] = json.dumps(
        {
            "user_id": 55,
            "updated_at": 1,
            "client_lane": "mobile",
        }
    )
    monkeypatch.setattr(kitty_session_redis, "get_async_redis", lambda: fake)
    monkeypatch.setattr(kitty_session_redis, "record_kitty_redis_persist", lambda: None)
    mark_mock = AsyncMock()
    monkeypatch.setattr(kitty_session_redis, "mark_kitty_mobile_active", mark_mock)

    await kitty_session_redis.upsert_kitty_redis_session(
        scope,
        55,
        active_diagram_library_id=scope,
        live_payload={"diagram_type": "circle_map", "diagram_data": {}},
        client_lane=None,
        preserve_mobile_lane=False,
    )

    stored = json.loads(fake.data[meta_key])
    assert "client_lane" not in stored
    mark_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_upsert_mobile_lane_marks_user_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test upsert mobile lane marks user active."""
    fake = _FakeRedis()
    scope = "mobile-scope"
    monkeypatch.setattr(kitty_session_redis, "get_async_redis", lambda: fake)
    monkeypatch.setattr(kitty_session_redis, "record_kitty_redis_persist", lambda: None)
    mark_mock = AsyncMock()
    monkeypatch.setattr(kitty_session_redis, "mark_kitty_mobile_active", mark_mock)

    await kitty_session_redis.upsert_kitty_redis_session(
        scope,
        88,
        active_diagram_library_id=None,
        live_payload={"diagram_type": "circle_map", "diagram_data": {}},
        client_lane="mobile",
        preserve_mobile_lane=True,
    )

    stored = json.loads(fake.data[kitty_sessionmeta_key(scope)])
    assert stored.get("client_lane") == "mobile"
    mark_mock.assert_awaited_once_with(88, scope)


@pytest.mark.asyncio
async def test_upsert_preserve_mobile_lane_does_not_mark_without_explicit_lane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test upsert preserve mobile lane does not mark without explicit lane."""
    fake = _FakeRedis()
    scope = "lib-diagram-uuid"
    meta_key = kitty_sessionmeta_key(scope)
    fake.data[meta_key] = json.dumps(
        {
            "user_id": 55,
            "updated_at": 1,
            "client_lane": "mobile",
        }
    )
    monkeypatch.setattr(kitty_session_redis, "get_async_redis", lambda: fake)
    monkeypatch.setattr(kitty_session_redis, "record_kitty_redis_persist", lambda: None)
    mark_mock = AsyncMock()
    monkeypatch.setattr(kitty_session_redis, "mark_kitty_mobile_active", mark_mock)

    await kitty_session_redis.upsert_kitty_redis_session(
        scope,
        55,
        active_diagram_library_id=scope,
        live_payload={"diagram_type": "circle_map", "diagram_data": {}},
        client_lane=None,
        preserve_mobile_lane=True,
    )

    stored = json.loads(fake.data[meta_key])
    assert stored.get("client_lane") == "mobile"
    mark_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_kitty_rest_desktop_pairing_inactive_long_poll_skips_pop() -> None:
    """Test kitty rest desktop pairing inactive long poll skips pop."""
    user = _kitty_user(5)
    pop_mock = AsyncMock(return_value={"kind": "open_canvas", "diagram_type": "mindmap"})
    with (
        patch("services.kitty.http.handlers.config") as cfg,
        patch(
            "services.kitty.http.handlers.kitty_http_allowed",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.kitty.http.handlers.read_kitty_mobile_active",
            AsyncMock(return_value={"active": False, "scopes": [], "primary_scope": None}),
        ),
        patch(
            "services.kitty.http.handlers.pop_kitty_desktop_action_wait",
            pop_mock,
        ),
    ):
        cfg.FEATURE_KITTY_WS_ENABLED = True
        out = await kitty_rest_desktop_pairing(user, wait_sec=25)

    assert out["active"] is False
    assert out["action"] is None
    pop_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_kitty_rest_desktop_pairing_inactive_instant_pop() -> None:
    """Test kitty rest desktop pairing inactive instant pop."""
    user = _kitty_user(5)
    pop_mock = AsyncMock(return_value={"kind": "open_library_diagram", "diagram_library_id": "abc-def-123"})
    with (
        patch("services.kitty.http.handlers.config") as cfg,
        patch(
            "services.kitty.http.handlers.kitty_http_allowed",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.kitty.http.handlers.read_kitty_mobile_active",
            AsyncMock(return_value={"active": False, "scopes": [], "primary_scope": None}),
        ),
        patch(
            "services.kitty.http.handlers.consume_kitty_desktop_action_explicit_drain",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.kitty.http.handlers.pop_kitty_desktop_action_wait",
            pop_mock,
        ),
    ):
        cfg.FEATURE_KITTY_WS_ENABLED = True
        out = await kitty_rest_desktop_pairing(user, wait_sec=0)

    assert out["active"] is False
    assert out["action"]["kind"] == "open_library_diagram"
    pop_mock.assert_awaited_once_with(5, 0, discard_stale=True)


@pytest.mark.asyncio
async def test_kitty_rest_desktop_pairing_inactive_instant_pop_without_explicit_flag() -> None:
    """Test kitty rest desktop pairing inactive instant pop without explicit flag."""
    user = _kitty_user(5)
    pop_mock = AsyncMock(return_value={"kind": "open_library_diagram", "diagram_library_id": "abc-def-123"})
    with (
        patch("services.kitty.http.handlers.config") as cfg,
        patch(
            "services.kitty.http.handlers.kitty_http_allowed",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.kitty.http.handlers.read_kitty_mobile_active",
            AsyncMock(return_value={"active": False, "scopes": [], "primary_scope": None}),
        ),
        patch(
            "services.kitty.http.handlers.consume_kitty_desktop_action_explicit_drain",
            AsyncMock(return_value=False),
        ),
        patch(
            "services.kitty.http.handlers.pop_kitty_desktop_action_wait",
            pop_mock,
        ),
    ):
        cfg.FEATURE_KITTY_WS_ENABLED = True
        out = await kitty_rest_desktop_pairing(user, wait_sec=0)

    assert out["active"] is False
    assert out["action"] is None
    pop_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_kitty_rest_desktop_pairing_active_long_poll_pop() -> None:
    """Test kitty rest desktop pairing active long poll pop."""
    user = _kitty_user(6)
    pop_mock = AsyncMock(return_value={"kind": "open_canvas", "diagram_type": "mindmap"})
    with (
        patch("services.kitty.http.handlers.config") as cfg,
        patch(
            "services.kitty.http.handlers.kitty_http_allowed",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.kitty.http.handlers.read_kitty_mobile_active",
            AsyncMock(
                return_value={
                    "active": True,
                    "scopes": ["scope-a"],
                    "primary_scope": "scope-a",
                }
            ),
        ),
        patch(
            "services.kitty.http.handlers.pop_kitty_desktop_action_wait",
            pop_mock,
        ),
    ):
        cfg.FEATURE_KITTY_WS_ENABLED = True
        out = await kitty_rest_desktop_pairing(user, wait_sec=25)

    assert out["active"] is True
    assert out["action"] == {"kind": "open_canvas", "diagram_type": "mindmap"}
    pop_mock.assert_awaited_once_with(6, 25, discard_stale=True)


@pytest.mark.asyncio
async def test_pop_wait_chunks_blpop_under_socket_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BLPOP block stays under REDIS_SOCKET_TIMEOUT to avoid client read timeouts."""

    class _QueueRedis:
        def __init__(self) -> None:
            """init  ."""
            self.blpop_timeouts: list[int] = []

        async def lpop(self, _key: str) -> None:
            """Lpop."""
            return None

        async def blpop(self, _key: str, timeout: int = 0) -> None:
            """Blpop."""
            self.blpop_timeouts.append(timeout)
            return None

    fake = _QueueRedis()
    clock = {"now": 100.0}

    async def blpop_advance(_key: str, timeout: int = 0) -> None:
        fake.blpop_timeouts.append(timeout)
        clock["now"] += float(timeout)
        return None

    monkeypatch.setattr(queue, "get_async_redis", lambda: fake)
    monkeypatch.setattr(queue, "get_async_redis_socket_timeout", lambda: 5.0)
    monkeypatch.setattr(queue.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(fake, "blpop", blpop_advance)

    result = await queue.pop_kitty_desktop_action_wait(3, wait_sec=25)
    assert result is None
    assert fake.blpop_timeouts
    assert all(timeout <= 4 for timeout in fake.blpop_timeouts)
    assert fake.blpop_timeouts[0] == 4
    assert len(fake.blpop_timeouts) >= 6


@pytest.mark.asyncio
async def test_kitty_rest_mobile_active_get_shape() -> None:
    """Test kitty rest mobile active get shape."""
    user = _kitty_user(12)
    with (
        patch("services.kitty.http.handlers.config") as cfg,
        patch(
            "services.kitty.http.handlers.kitty_http_allowed",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.kitty.http.handlers.read_kitty_mobile_active",
            AsyncMock(
                return_value={
                    "active": True,
                    "scopes": ["abc"],
                    "primary_scope": "abc",
                }
            ),
        ),
    ):
        cfg.FEATURE_KITTY_WS_ENABLED = True
        out = await kitty_rest_mobile_active_get(user)

    assert out == {"active": True, "scopes": ["abc"], "primary_scope": "abc"}


@pytest.mark.asyncio
async def test_mark_publishes_desktop_wake(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test mark publishes desktop wake."""
    fake = _FakeRedis()
    publish_mock = AsyncMock()
    _patch_kitty_redis(monkeypatch, fake)
    monkeypatch.setattr(kitty_mobile_active, "_emit_desktop_wake", publish_mock)

    await kitty_mobile_active.mark_kitty_mobile_active(42, "scope-a")

    publish_mock.assert_awaited_once()
    args = publish_mock.await_args
    assert args is not None
    assert args.args[0] == 42
    assert args.args[1]["active"] is True
    assert args.args[1]["scopes"] == ["scope-a"]


@pytest.mark.asyncio
async def test_clear_publishes_inactive_wake(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test clear publishes inactive wake."""
    fake = _FakeRedis()
    publish_mock = AsyncMock()
    _patch_kitty_redis(monkeypatch, fake)
    monkeypatch.setattr(kitty_mobile_active, "_emit_desktop_wake", publish_mock)

    await kitty_mobile_active.mark_kitty_mobile_active(7, "scope-x")
    publish_mock.reset_mock()
    await kitty_mobile_active.clear_kitty_mobile_scope(7, "scope-x")

    publish_mock.assert_awaited_once()
    args = publish_mock.await_args
    assert args is not None
    assert args.args[1]["active"] is False


def test_build_desktop_wake_payload_shape() -> None:
    """Test build desktop wake payload shape."""
    raw = build_kitty_desktop_wake_payload({"active": True, "scopes": ["a"], "primary_scope": "a"})
    data = json.loads(raw)
    assert data["type"] == "mobile_active"
    assert data["active"] is True
    assert data["scopes"] == ["a"]
    assert data["primary_scope"] == "a"


@pytest.mark.asyncio
async def test_kitty_rest_desktop_action_pop_inactive_long_poll_skips_queue() -> None:
    """Test kitty rest desktop action pop inactive long poll skips queue."""
    user = _kitty_user(8)
    pop_mock = AsyncMock(return_value={"kind": "open_canvas", "diagram_type": "mindmap"})
    with (
        patch("services.kitty.http.handlers.config") as cfg,
        patch(
            "services.kitty.http.handlers.kitty_http_allowed",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.kitty.http.handlers.read_kitty_mobile_active",
            AsyncMock(return_value={"active": False, "scopes": [], "primary_scope": None}),
        ),
        patch(
            "services.kitty.http.handlers.pop_kitty_desktop_action_wait",
            pop_mock,
        ),
    ):
        cfg.FEATURE_KITTY_WS_ENABLED = True
        out = await kitty_rest_desktop_action_pop(user, wait_sec=25)

    assert out == {"action": None}
    pop_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_kitty_rest_desktop_action_pop_inactive_instant_pop() -> None:
    """Test kitty rest desktop action pop inactive instant pop."""
    user = _kitty_user(8)
    pop_mock = AsyncMock(return_value={"kind": "open_library_diagram", "diagram_library_id": "abc-def-123"})
    with (
        patch("services.kitty.http.handlers.config") as cfg,
        patch(
            "services.kitty.http.handlers.kitty_http_allowed",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.kitty.http.handlers.read_kitty_mobile_active",
            AsyncMock(return_value={"active": False, "scopes": [], "primary_scope": None}),
        ),
        patch(
            "services.kitty.http.handlers.consume_kitty_desktop_action_explicit_drain",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.kitty.http.handlers.pop_kitty_desktop_action_wait",
            pop_mock,
        ),
    ):
        cfg.FEATURE_KITTY_WS_ENABLED = True
        out = await kitty_rest_desktop_action_pop(user, wait_sec=0)

    assert out["action"]["kind"] == "open_library_diagram"
    pop_mock.assert_awaited_once_with(8, 0, discard_stale=True)


@pytest.mark.asyncio
async def test_kitty_rest_mobile_active_disabled_returns_inactive() -> None:
    """Test kitty rest mobile active disabled returns inactive."""
    user = _kitty_user(3)
    with patch("services.kitty.http.handlers.config") as cfg:
        cfg.FEATURE_KITTY_WS_ENABLED = False
        out = await kitty_rest_mobile_active_get(user)

    assert out == {"active": False, "scopes": [], "primary_scope": None}


@pytest.mark.asyncio
async def test_enqueue_open_library_diagram_accepts_valid_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test enqueue open library diagram accepts valid id."""
    pushed: list[dict] = []

    async def _fake_push(user_id: int, payload: dict) -> bool:
        pushed.append({"user_id": user_id, "payload": payload})
        return True

    monkeypatch.setattr(queue, "_push_desktop_action", _fake_push)
    ok = await queue.enqueue_kitty_desktop_action(
        9,
        {
            "kind": "open_library_diagram",
            "diagram_library_id": "abc-def-123",
            "title": "My topic",
        },
    )
    assert ok is True
    assert pushed[0]["user_id"] == 9
    assert pushed[0]["payload"]["kind"] == "open_library_diagram"
    assert pushed[0]["payload"]["diagram_library_id"] == "abc-def-123"
    assert pushed[0]["payload"]["title"] == "My topic"


@pytest.mark.asyncio
async def test_pop_discards_stale_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test pop discards stale actions."""
    stale = json.dumps(
        {
            "kind": "open_canvas",
            "diagram_type": "mindmap",
            "enqueued_at": int(time.time()) - 500,
        }
    )
    fresh = json.dumps(
        {
            "kind": "open_library_diagram",
            "diagram_library_id": "abc-def-123",
            "enqueued_at": int(time.time()),
        }
    )

    class _QueueRedis:
        def __init__(self) -> None:
            """init  ."""
            self.items = [stale.encode("utf-8"), fresh.encode("utf-8")]

        async def lpop(self, _key: str) -> bytes | None:
            """Lpop."""
            if not self.items:
                return None
            return self.items.pop(0)

    fake = _QueueRedis()
    monkeypatch.setattr(queue, "get_async_redis", lambda: fake)
    out = await queue.pop_kitty_desktop_action_wait(4, wait_sec=0, discard_stale=True)
    assert out is not None
    assert out["kind"] == "open_library_diagram"


@pytest.mark.asyncio
async def test_enqueue_open_library_diagram_rejects_invalid_id() -> None:
    """Test enqueue open library diagram rejects invalid id."""
    ok = await queue.enqueue_kitty_desktop_action(
        9,
        {"kind": "open_library_diagram", "diagram_library_id": "bad id!"},
    )
    assert ok is False


@pytest.mark.asyncio
async def test_kitty_rest_desktop_action_enqueue_ok() -> None:
    """Test kitty rest desktop action enqueue ok."""
    user = _kitty_user(7)
    enqueue_mock = AsyncMock(return_value=True)
    wake_mock = AsyncMock()
    explicit_mock = AsyncMock()
    with (
        patch("services.kitty.http.handlers.config") as cfg,
        patch(
            "services.kitty.http.handlers.kitty_http_allowed",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.kitty.http.handlers.enqueue_kitty_desktop_action",
            enqueue_mock,
        ),
        patch(
            "services.kitty.http.handlers.mark_kitty_desktop_action_explicit_drain",
            explicit_mock,
        ),
        patch(
            "services.kitty.http.handlers.publish_kitty_desktop_action_pending",
            wake_mock,
        ),
    ):
        cfg.FEATURE_KITTY_WS_ENABLED = True
        out = await kitty_rest_desktop_action_enqueue(
            user,
            {
                "kind": "open_library_diagram",
                "diagram_library_id": "scope-1",
                "title": "Cars",
            },
        )

    assert out == {"ok": True}
    enqueue_mock.assert_awaited_once()
    explicit_mock.assert_awaited_once_with(7)
    wake_mock.assert_awaited_once_with(7)
