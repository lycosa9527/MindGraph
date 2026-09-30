"""Saved seminar lines survive a full fan-out delivery queue."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import MagicMock

from services.features import ws_redis_fanout_listener as lst
from services.features.mindmate_collab.ws_registry import (
    ACTIVE_CONNECTIONS,
    MindmateCollabWsHandle,
    enqueue_transcript_resync,
)

_enqueue_fanout_payload = getattr(lst, "_enqueue_fanout_payload")
_put_fanout = getattr(lst, "_put_fanout")
_workshop_inner_type = getattr(lst, "_workshop_inner_type")
KIND_WS = getattr(lst, "_KIND_WS")
_on_fanout_subscribed = getattr(lst, "_on_fanout_subscribed")


def _frame(frame_type: str) -> str:
    """Workshop envelope whose inner frame has the given type."""
    return json.dumps(
        {
            "v": 1,
            "k": "ws",
            "d": json.dumps({"type": frame_type}),
        },
    )


def _queued_types(queue: asyncio.Queue[tuple[str, str]]) -> list[str]:
    """Inner frame types currently sitting in the delivery queue."""
    found: list[str] = []
    while True:
        try:
            _kind, payload = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        found.append(_workshop_inner_type(payload))
    return found


def test_full_queue_keeps_saved_line_over_stream_chunk() -> None:
    """A user line replaces a queued stream chunk instead of being dropped."""
    queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=1)
    assert _put_fanout(queue, KIND_WS, _frame("ai_message_chunk"))
    _enqueue_fanout_payload(queue, KIND_WS, _frame("user_message"))
    assert _queued_types(queue) == ["user_message"]


def test_stream_chunk_is_dropped_when_saved_line_fills_queue() -> None:
    """Stream tokens yield the slot; a saved line already queued stays."""
    queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=1)
    assert _put_fanout(queue, KIND_WS, _frame("user_message"))
    _enqueue_fanout_payload(queue, KIND_WS, _frame("ai_message_chunk"))
    assert _queued_types(queue) == ["user_message"]


def test_session_end_bypasses_queue_when_no_chunk_can_be_dropped(monkeypatch: Any) -> None:
    """Ending the seminar still reaches open sockets when the queue is full of saved lines."""
    delivered: list[str] = []
    monkeypatch.setattr(lst, "_schedule_critical_workshop_delivery", delivered.append)
    queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=1)
    ending = _frame("session_ended_shutdown")
    assert _put_fanout(queue, KIND_WS, _frame("user_message"))
    _enqueue_fanout_payload(queue, KIND_WS, ending)
    assert delivered == [ending]


def test_saved_line_bypasses_queue_when_no_chunk_can_be_dropped(monkeypatch: Any) -> None:
    """Two saved lines and a full queue deliver the new line immediately."""
    delivered: list[str] = []
    monkeypatch.setattr(lst, "_schedule_critical_workshop_delivery", delivered.append)
    queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=1)
    second = _frame("ai_message_end")
    assert _put_fanout(queue, KIND_WS, _frame("user_message"))
    _enqueue_fanout_payload(queue, KIND_WS, second)
    assert delivered == [second]
    assert _queued_types(queue) == ["user_message"]


def test_transcript_resync_skips_sockets_still_joining() -> None:
    """A resync must not land ahead of the join snapshot."""
    joining = MindmateCollabWsHandle(MagicMock())
    joining.accepts_fanout = False
    live = MindmateCollabWsHandle(MagicMock())
    ACTIVE_CONNECTIONS["mmc:ABC"] = {1: joining, 2: live}
    try:
        enqueue_transcript_resync()
        assert joining.send_queue.empty()
        _kind, payload = live.send_queue.get_nowait()
        assert json.loads(payload)["type"] == "resync"
    finally:
        ACTIVE_CONNECTIONS.clear()


def test_on_fanout_subscribed_asks_open_seminars(monkeypatch: Any) -> None:
    """A fresh pub/sub subscription is the event that heals a listener gap."""
    calls = {"n": 0}

    def _mark() -> None:
        calls["n"] += 1

    monkeypatch.setattr(lst, "notify_collab_fanout_subscribed", _mark)
    _on_fanout_subscribed()
    assert calls["n"] == 1
