"""
Local SSE seats for one shared diagram.

This module stays free of the lease and fan-out imports so workers can push a
roster without a cycle.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from services.diagram_shares.queue import ShareTab, ShareTabStatus, tab_status

_QUEUE_SIZE = 8


@dataclass
class _Seat:
    """One browser tab waiting for role changes."""

    user_id: int
    tab_id: str
    queue: asyncio.Queue[str]


_seats: dict[str, list[_Seat]] = {}


def _frame(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def role_event(status: ShareTabStatus) -> str:
    """SSE frame for who may edit."""
    return _frame(
        {
            "type": "role",
            "role": status["role"],
            "editor_name": status["editor_name"],
            "viewer_count": status["viewer_count"],
            "skipped": False,
        }
    )


DENIED_EVENT = _frame({"type": "denied"})
REPLACED_EVENT = _frame({"type": "replaced"})
SKIPPED_EVENT = _frame(
    {
        "type": "role",
        "role": "editor",
        "editor_name": "",
        "viewer_count": 0,
        "skipped": True,
    }
)


def _offer(queue: asyncio.Queue[str], text: str) -> None:
    if queue.full():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    try:
        queue.put_nowait(text)
    except asyncio.QueueFull:
        pass


def register_seat(diagram_id: str, user_id: int, tab_id: str) -> _Seat:
    """Subscribe one SSE response to roster changes for this diagram."""
    seat = _Seat(user_id=user_id, tab_id=tab_id, queue=asyncio.Queue(maxsize=_QUEUE_SIZE))
    _seats.setdefault(diagram_id, []).append(seat)
    return seat


def unregister_seat(diagram_id: str, seat: _Seat) -> None:
    """Drop a closed SSE response."""
    seats = _seats.get(diagram_id)
    if not seats:
        return
    remaining = [item for item in seats if item is not seat]
    if remaining:
        _seats[diagram_id] = remaining
        return
    _seats.pop(diagram_id, None)


def push_roster(diagram_id: str, tabs: list[ShareTab]) -> None:
    """Push each local stream its own role, or a denial when it lost the slot."""
    for seat in list(_seats.get(diagram_id, ())):
        status = tab_status(tabs, seat.user_id, seat.tab_id)
        if not status["present"]:
            _offer(seat.queue, DENIED_EVENT)
            continue
        _offer(seat.queue, role_event(status))
