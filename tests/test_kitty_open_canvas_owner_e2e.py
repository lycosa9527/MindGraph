"""End-to-end: open_canvas scope SoT → canvas-owner presence → verified edit ack.

Reproduces the production failure mode from app.2026-07-12 logs:
mobile invents ephemeral scope, desktop must adopt it and register as canvas owner
before verified update_center can apply/ack (not ack_timeout / FEATURE_KITTY red herring).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.diagram_edit.ack import complete_mutation_ack_from_client
from services.diagram_edit.pending import (
    MutationAckPayload,
    complete_pending,
    new_mutation_id,
    register_pending,
    reset_pending_state_for_tests,
)
from services.kitty.context.messaging import send_kitty_diagram_update
from services.kitty.infra.desktop import kitty_canvas_owner_presence as presence_mod
from services.kitty.infra.desktop import kitty_desktop_action_queue as queue
from services.kitty.infra.desktop.kitty_desktop_wake_fanout import publish_kitty_diagram_update
from services.kitty.session.canvas_owner import canvas_owner_available
from services.kitty.session.runtime_state import voice_sessions


class _FakeRedis:
    """Minimal async Redis for presence + pub/sub tests."""

    def __init__(self) -> None:
        """Init in-memory store and publish log."""
        self.store: Dict[str, str] = {}
        self.published: List[tuple[str, str]] = []

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """SET key with optional TTL (TTL ignored in fake)."""
        del ex
        self.store[key] = value
        return True

    async def get(self, key: str) -> Optional[str]:
        """GET key."""
        return self.store.get(key)

    async def delete(self, key: str) -> int:
        """DELETE key."""
        return 1 if self.store.pop(key, None) is not None else 0

    async def publish(self, channel: str, payload: str) -> int:
        """PUBLISH to channel."""
        self.published.append((channel, payload))
        return 1


@pytest.fixture(autouse=True)
def _reset_pending() -> Iterator[None]:
    """Clear pending mutation registry and voice sessions between tests."""
    reset_pending_state_for_tests()
    yield
    reset_pending_state_for_tests()
    voice_sessions.clear()


@pytest.mark.asyncio
async def test_open_canvas_enqueue_preserves_session_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mobile open_canvas must carry the ephemeral Kitty scope for desktop adopt."""
    pushed: list[dict] = []

    async def _fake_push(user_id: int, payload: dict) -> bool:
        pushed.append({"user_id": user_id, "payload": payload})
        return True

    monkeypatch.setattr(queue, "_push_desktop_action", _fake_push)
    scope = "101327e1-2226-4483-b376-8824bccfeb73"
    ok = await queue.enqueue_kitty_desktop_action(
        3,
        {
            "kind": "open_canvas",
            "diagram_type": "mindmap",
            "session_scope": scope,
        },
    )
    assert ok is True
    assert pushed[0]["payload"]["session_scope"] == scope


@pytest.mark.asyncio
async def test_open_canvas_rejects_unsafe_session_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unsafe session_scope is stripped; open_canvas still enqueues type-only."""
    pushed: list[dict] = []

    async def _fake_push(user_id: int, payload: dict) -> bool:
        pushed.append({"user_id": user_id, "payload": payload})
        return True

    monkeypatch.setattr(queue, "_push_desktop_action", _fake_push)
    ok = await queue.enqueue_kitty_desktop_action(
        3,
        {
            "kind": "open_canvas",
            "diagram_type": "mindmap",
            "session_scope": "bad scope!",
        },
    )
    assert ok is True
    assert "session_scope" not in pushed[0]["payload"]


@pytest.mark.asyncio
async def test_canvas_owner_presence_lease_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Desktop owner mark/clear is visible via Redis presence (cross-worker)."""
    fake = _FakeRedis()
    monkeypatch.setattr(presence_mod, "get_async_redis", lambda: fake)
    scope = "lib-owner-e2e"
    assert await presence_mod.has_kitty_canvas_owner_present(7, scope) is False
    await presence_mod.mark_kitty_canvas_owner_present(7, scope)
    assert await presence_mod.has_kitty_canvas_owner_present(7, scope) is True
    assert await canvas_owner_available(7, scope) is True
    await presence_mod.clear_kitty_canvas_owner_present(7, scope)
    assert await presence_mod.has_kitty_canvas_owner_present(7, scope) is False


@pytest.mark.asyncio
async def test_verified_edit_fail_closed_without_owner_presence() -> None:
    """
    Mobile verified update with no desktop owner must complete pending as no_owner
    (not hang until ack_timeout).
    """
    mobile_ws = AsyncMock()
    mobile_ws.send_json = AsyncMock()
    scope = "101327e1-2226-4483-b376-8824bccfeb73"
    vid = "voice_mobile_e2e"
    voice_sessions[vid] = {
        "user_id": 3,
        "diagram_session_id": scope,
        "_kitty_client_lane": "mobile",
        "_kitty_canvas_owner": False,
        "_client_websocket": mobile_ws,
        "context": {"language": "zh"},
    }
    mutation_id = new_mutation_id()
    fut = register_pending(mutation_id, vid)

    with (
        patch(
            "services.kitty.context.messaging.canvas_owner_available",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "services.kitty.context.messaging.publish_kitty_diagram_update",
            new=AsyncMock(return_value=True),
        ) as publish_mock,
    ):
        sent = await send_kitty_diagram_update(
            mobile_ws,
            vid,
            {
                "type": "diagram_update",
                "action": "update_center",
                "updates": {"new_text": "中国"},
                "mutation_id": mutation_id,
                "user_summary": "主题已更新",
            },
        )

    assert sent is True
    publish_mock.assert_not_awaited()
    assert fut.done()
    ack = fut.result()
    assert isinstance(ack, MutationAckPayload)
    assert ack.verified is False
    assert ack.error_code == "no_owner"


@pytest.mark.asyncio
async def test_verified_edit_sse_fallback_when_owner_present_cross_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Cross-worker path: no local owner WS, Redis presence set → SSE fanout + ack works.
    """
    fake = _FakeRedis()
    monkeypatch.setattr(presence_mod, "get_async_redis", lambda: fake)
    monkeypatch.setattr(
        "services.kitty.infra.desktop.kitty_desktop_wake_fanout.get_async_redis",
        lambda: fake,
    )

    mobile_ws = AsyncMock()
    mobile_ws.send_json = AsyncMock()
    scope = "101327e1-2226-4483-b376-8824bccfeb73"
    uid = 3
    vid = "voice_mobile_cross"
    voice_sessions[vid] = {
        "user_id": uid,
        "diagram_session_id": scope,
        "_kitty_client_lane": "mobile",
        "_kitty_canvas_owner": False,
        "_client_websocket": mobile_ws,
        "context": {"language": "zh"},
    }

    await presence_mod.mark_kitty_canvas_owner_present(uid, scope)
    mutation_id = new_mutation_id()
    fut = register_pending(mutation_id, vid)

    sent = await send_kitty_diagram_update(
        mobile_ws,
        vid,
        {
            "type": "diagram_update",
            "action": "update_center",
            "updates": {"new_text": "中国"},
            "mutation_id": mutation_id,
            "user_summary": "主题已更新",
        },
    )
    assert sent is True

    # Desktop wake SSE carries verified mutation for the owning tab.
    wake_msgs = [json.loads(p) for _ch, p in fake.published]
    diagram_updates = [m for m in wake_msgs if m.get("type") == "diagram_update"]
    assert len(diagram_updates) == 1
    assert diagram_updates[0]["mutation_id"] == mutation_id
    assert diagram_updates[0]["scope"] == scope

    # Desktop owner applies and acks (same process pending future).
    assert complete_mutation_ack_from_client(
        {
            "mutation_id": mutation_id,
            "verified": True,
            "ok": True,
            "revision": 1,
        }
    )
    assert fut.done()
    ack = fut.result()
    assert isinstance(ack, MutationAckPayload)
    assert ack.verified is True


@pytest.mark.asyncio
async def test_e2e_open_canvas_scope_to_verified_center_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Full chain matching the morning incident:
    1) mobile enqueues open_canvas with session_scope
    2) desktop marks canvas-owner presence for that scope
    3) mobile verified update_center uses SSE fallback and receives ack
    """
    fake = _FakeRedis()
    pushed: list[dict] = []

    async def _fake_push(_user_id: int, payload: dict) -> bool:
        pushed.append(payload)
        return True

    monkeypatch.setattr(queue, "_push_desktop_action", _fake_push)
    monkeypatch.setattr(presence_mod, "get_async_redis", lambda: fake)
    monkeypatch.setattr(
        "services.kitty.infra.desktop.kitty_desktop_wake_fanout.get_async_redis",
        lambda: fake,
    )

    scope = "101327e1-2226-4483-b376-8824bccfeb73"
    uid = 3

    ok = await queue.enqueue_kitty_desktop_action(
        uid,
        {"kind": "open_canvas", "diagram_type": "mindmap", "session_scope": scope},
    )
    assert ok is True
    assert pushed[0]["session_scope"] == scope

    # Desktop adopted scope and opened canvas-owner WS (presence lease).
    await presence_mod.mark_kitty_canvas_owner_present(uid, scope)
    assert await canvas_owner_available(uid, scope) is True

    mobile_ws = AsyncMock()
    mobile_ws.send_json = AsyncMock()
    vid = "voice_e2e_chain"
    voice_sessions[vid] = {
        "user_id": uid,
        "diagram_session_id": scope,
        "_kitty_client_lane": "mobile",
        "_kitty_canvas_owner": False,
        "_client_websocket": mobile_ws,
        "context": {"language": "zh"},
    }
    mutation_id = new_mutation_id()
    fut = register_pending(mutation_id, vid)

    sent = await send_kitty_diagram_update(
        mobile_ws,
        vid,
        {
            "type": "diagram_update",
            "action": "update_center",
            "updates": {"new_text": "中国"},
            "mutation_id": mutation_id,
        },
    )
    assert sent is True

    wake_payloads = [json.loads(p) for _ch, p in fake.published]
    assert any(
        m.get("type") == "diagram_update" and m.get("mutation_id") == mutation_id
        for m in wake_payloads
    )

    complete_pending(
        MutationAckPayload(mutation_id=mutation_id, verified=True, revision=2)
    )
    assert fut.done()
    ack = fut.result()
    assert isinstance(ack, MutationAckPayload)
    assert ack.verified is True


@pytest.mark.asyncio
async def test_publish_verified_diagram_update_keeps_mutation_id() -> None:
    """SSE payload must retain mutation_id for desktop apply+ack."""
    redis = MagicMock()
    published: list[str] = []

    async def _publish(_channel: str, payload: str) -> int:
        published.append(payload)
        return 1

    redis.publish = _publish
    with patch(
        "services.kitty.infra.desktop.kitty_desktop_wake_fanout.get_async_redis",
        return_value=redis,
    ):
        await publish_kitty_diagram_update(
            3,
            "scope-x",
            {
                "type": "diagram_update",
                "action": "update_center",
                "mutation_id": "mid-1",
                "updates": {"new_text": "中国"},
            },
        )
    body = json.loads(published[0])
    assert body["mutation_id"] == "mid-1"
    assert body["action"] == "update_center"
