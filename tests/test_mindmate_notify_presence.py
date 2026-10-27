"""MindMate notify presence uses the same org fan-out as workshop chat."""

from __future__ import annotations

import json
from typing import Any, Dict, List, cast

import pytest
from fastapi import WebSocket
from fastapi.websockets import WebSocketState

from services.features.mindmate_notify_ws_manager import mindmate_notify_ws_manager
from services.features.workshop_chat_presence_store import user_ids_from_presence_members


class _QuietSocket:
    """Stand-in socket that is already closed, so connect does not close it."""

    client_state = WebSocketState.DISCONNECTED


@pytest.mark.asyncio
async def test_broadcast_publishes_presence_when_fanout_is_on(monkeypatch) -> None:
    """A live status change is a Redis ``po`` frame, not a local-only send."""
    published: List[Dict[str, Any]] = []
    local: List[int] = []

    async def fake_publish(envelope: Dict[str, Any]) -> None:
        published.append(envelope)

    async def fake_local(org_id: int, exclude_user: int | None, data: str) -> None:
        del exclude_user, data
        local.append(org_id)

    monkeypatch.setattr(
        "services.features.mindmate_notify_ws_manager.is_ws_fanout_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "services.features.mindmate_notify_ws_manager.publish_chat_fanout_async",
        fake_publish,
    )
    monkeypatch.setattr(mindmate_notify_ws_manager, "deliver_local_presence_org", fake_local)

    await mindmate_notify_ws_manager.broadcast_org_presence(4, "active", 9, exclude_user=4)

    assert not local
    assert len(published) == 1
    assert published[0]["k"] == "po"
    assert published[0]["oid"] == 9
    assert published[0]["ex"] == 4
    body = json.loads(published[0]["d"])
    assert body["user_id"] == 4
    assert body["status"] == "active"


@pytest.mark.asyncio
async def test_a_replaced_notify_socket_keeps_presence(monkeypatch) -> None:
    """Closing the old tab must not unregister the socket that replaced it."""
    removed: List[int] = []

    async def fake_remove(org_id: int, user_id: int, *, source: str) -> bool:
        del user_id, source
        removed.append(org_id)
        return False

    async def fake_touch(org_id: int, user_id: int, *, source: str) -> None:
        del org_id, user_id, source

    store = "services.features.mindmate_notify_ws_manager.workshop_chat_presence_store"
    monkeypatch.setattr(f"{store}.remove_presence_org_user", fake_remove)
    monkeypatch.setattr(f"{store}.touch_presence_org_user", fake_touch)

    first = cast(WebSocket, _QuietSocket())
    second = cast(WebSocket, _QuietSocket())
    user_id = 910041
    await mindmate_notify_ws_manager.connect(user_id, first)
    await mindmate_notify_ws_manager.set_presence_orgs(user_id, [9])
    await mindmate_notify_ws_manager.connect(user_id, second)

    stale = await mindmate_notify_ws_manager.disconnect(user_id, first)
    assert stale == []
    assert not removed
    assert mindmate_notify_ws_manager.get_presence_org_id(user_id) == 9

    gone = await mindmate_notify_ws_manager.disconnect(user_id, second)
    assert gone == [9]
    assert removed == [9]
    assert mindmate_notify_ws_manager.get_presence_org_id(user_id) is None


@pytest.mark.asyncio
async def test_notify_disconnect_keeps_a_workshop_presence(monkeypatch) -> None:
    """Closing MindMate must not mark someone offline while workshop chat is up."""
    broadcasts: List[str] = []

    async def fake_remove(org_id: int, user_id: int, *, source: str) -> bool:
        del org_id, user_id, source
        return True

    async def fake_touch(org_id: int, user_id: int, *, source: str) -> None:
        del org_id, user_id, source

    async def fake_broadcast(
        user_id: int,
        status: str,
        org_id: int,
        *,
        exclude_user: int | None = None,
    ) -> None:
        del user_id, org_id, exclude_user
        broadcasts.append(status)

    store = "services.features.mindmate_notify_ws_manager.workshop_chat_presence_store"
    monkeypatch.setattr(f"{store}.remove_presence_org_user", fake_remove)
    monkeypatch.setattr(f"{store}.touch_presence_org_user", fake_touch)
    monkeypatch.setattr(mindmate_notify_ws_manager, "broadcast_org_presence", fake_broadcast)

    socket = cast(WebSocket, _QuietSocket())
    user_id = 910042
    await mindmate_notify_ws_manager.connect(user_id, socket)
    await mindmate_notify_ws_manager.set_presence_orgs(user_id, [9])
    gone = await mindmate_notify_ws_manager.disconnect(user_id, socket)
    assert gone == []
    assert not broadcasts


def test_presence_members_collapse_sources_to_user_ids() -> None:
    """Workshop and MindMate sockets for one person are a single online id."""
    online = user_ids_from_presence_members(
        ["4", b"4:workshop", "9:notify", "bad", "0:notify", b"12:notify"],
    )
    assert online == {4, 9, 12}
