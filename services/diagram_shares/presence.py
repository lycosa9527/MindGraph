"""
SSE presence for one shared diagram.

The open response holds the edit slot. A dropped connection leaves after a
short grace so a reconnect keeps its place. Redis TTL only covers a killed process.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator

from services.diagram_shares.access import diagram_has_grants, library_access
from services.diagram_shares.lease import join_lease, leave_lease, touch_lease
from services.diagram_shares.seats import (
    DENIED_EVENT,
    REPLACED_EVENT,
    SKIPPED_EVENT,
    register_seat,
    role_event,
    unregister_seat,
)
from services.online_collab.core.online_collab_manager import get_online_collab_manager

logger = logging.getLogger(__name__)

PING_SECONDS = 5
_LEAVE_GRACE_SECONDS = 3
_LeaveKey = tuple[str, int, str, int]
_pending_leaves: dict[_LeaveKey, asyncio.Task[None]] = {}


def _cancel_share_leave(diagram_id: str, user_id: int, tab_id: str, epoch: int) -> None:
    """Drop a deferred leave once this tab has opened a new stream."""
    task = _pending_leaves.pop((diagram_id, user_id, tab_id, epoch), None)
    if task is not None:
        task.cancel()


def _schedule_share_leave(diagram_id: str, user_id: int, tab_id: str, epoch: int, stream: int) -> None:
    """Leave after a short grace so a reconnect can keep this tab's place."""
    key = (diagram_id, user_id, tab_id, epoch)
    previous = _pending_leaves.get(key)

    async def _leave_later() -> None:
        try:
            await asyncio.sleep(_LEAVE_GRACE_SECONDS)
            await leave_lease(diagram_id, user_id, tab_id, epoch, stream)
        finally:
            if _pending_leaves.get(key) is asyncio.current_task():
                _pending_leaves.pop(key, None)

    _pending_leaves[key] = asyncio.create_task(_leave_later())
    if previous is not None:
        previous.cancel()


async def _collab_active(diagram_id: str) -> bool:
    """Live workshop sessions use their own editor, not this queue."""
    code = await get_online_collab_manager().get_active_online_collab_code_for_diagram(diagram_id)
    return bool(code)


async def _owner_without_grants(user_id: int, diagram_id: str, role: str) -> bool:
    """An owner with nobody else in the library edits alone."""
    if role != "owner":
        return False
    return not await diagram_has_grants(user_id, diagram_id)


async def _join_step(
    diagram_id: str,
    user_id: int,
    tab_id: str,
    epoch: int,
    name: str,
    stream: int,
) -> tuple[str, str]:
    """Decide whether this connection should hold a queue slot."""
    access = await library_access(user_id, diagram_id)
    if access.role == "none":
        if access.uncertain:
            return "wait", ""
        return "denied", DENIED_EVENT
    if await _owner_without_grants(user_id, diagram_id, access.role):
        return "skipped", SKIPPED_EVENT
    _cancel_share_leave(diagram_id, user_id, tab_id, epoch)
    status = await join_lease(diagram_id, user_id, tab_id, name, epoch, stream)
    if status is None:
        return "wait", ""
    if not status["present"]:
        return "replaced", REPLACED_EVENT
    return "joined", role_event(status)


async def iter_diagram_share_events(
    diagram_id: str,
    user_id: int,
    tab_id: str,
    epoch: int,
    name: str,
) -> AsyncIterator[str]:
    """Yield role events until the browser closes this response."""
    yield ": stream_open\nretry: 1000\n\n"
    seat = register_seat(diagram_id, user_id, tab_id)
    stream = time.time_ns()
    joined = False
    told_skip = False
    try:
        while True:
            if await _collab_active(diagram_id):
                if joined:
                    await leave_lease(diagram_id, user_id, tab_id, epoch, stream)
                    joined = False
                if told_skip:
                    yield ": ping\n\n"
                else:
                    told_skip = True
                    yield SKIPPED_EVENT
                await asyncio.sleep(PING_SECONDS)
                continue
            if not joined:
                action, payload = await _join_step(diagram_id, user_id, tab_id, epoch, name, stream)
                if action in {"denied", "replaced"}:
                    yield payload
                    return
                if action == "wait":
                    await asyncio.sleep(PING_SECONDS)
                    continue
                if action == "skipped":
                    if told_skip:
                        yield ": ping\n\n"
                    else:
                        told_skip = True
                        yield payload
                    await asyncio.sleep(PING_SECONDS)
                    continue
                told_skip = False
                joined = True
                yield payload
            try:
                incoming = await asyncio.wait_for(seat.queue.get(), timeout=PING_SECONDS)
            except asyncio.TimeoutError:
                touched = await touch_lease(diagram_id, user_id, tab_id, epoch, stream)
                if touched == "replaced":
                    joined = False
                    yield REPLACED_EVENT
                    return
                if touched == "missing":
                    joined = False
                    continue
                yield ": ping\n\n"
                continue
            yield incoming
            if incoming == DENIED_EVENT:
                return
    finally:
        unregister_seat(diagram_id, seat)
        if joined:
            _schedule_share_leave(diagram_id, user_id, tab_id, epoch, stream)
            logger.debug("[DiagramShare] SSE closed diagram=%s user=%s", diagram_id, user_id)
