"""One cancellable Kitty turn Task per voice session.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any, Optional

from services.kitty.session.memory import get_session_memory
from services.kitty.session.runtime_state import voice_sessions

logger = logging.getLogger(__name__)

TURN_TASK_KEY = "_kitty_turn_task"
TURN_GENERATION_KEY = "_kitty_turn_generation"


def turn_generation(voice_session_id: str) -> int:
    """Current turn generation. Stale work must stop after a bump."""
    sess = voice_sessions.get(voice_session_id)
    if not isinstance(sess, dict):
        return 0
    raw = sess.get(TURN_GENERATION_KEY)
    try:
        return int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        return 0


def bump_turn_generation(voice_session_id: str) -> int:
    """Invalidate in-flight turn work. Returns the new generation."""
    sess = voice_sessions.get(voice_session_id)
    if not isinstance(sess, dict):
        return 0
    nxt = turn_generation(voice_session_id) + 1
    sess[TURN_GENERATION_KEY] = nxt
    return nxt


def turn_generation_is_current(voice_session_id: str, generation: int) -> bool:
    """True when ``generation`` still matches the session counter."""
    return generation == turn_generation(voice_session_id)


def _record_interrupted(voice_session_id: str, reason: str) -> None:
    label = reason.strip() or "user"
    get_session_memory(voice_session_id).append_observation(
        f"interrupted:{label}",
        action="abort",
    )


async def cancel_active_turn(voice_session_id: str, *, reason: str = "user") -> bool:
    """Cancel the in-flight turn Task and write one interrupted observation.

    Returns True when a live Task was cancelled.
    """
    bump_turn_generation(voice_session_id)
    sess = voice_sessions.get(voice_session_id)
    if not isinstance(sess, dict):
        return False
    raw = sess.get(TURN_TASK_KEY)
    sess[TURN_TASK_KEY] = None
    if not isinstance(raw, asyncio.Task) or raw.done():
        return False
    _record_interrupted(voice_session_id, reason)
    raw.cancel()
    try:
        await raw
    except asyncio.CancelledError:
        logger.info(
            "Kitty turn cancelled sid=%s reason=%s",
            voice_session_id[:12],
            reason,
        )
    return True


async def run_cancellable_turn(
    voice_session_id: str,
    coro: Coroutine[Any, Any, Any],
) -> Optional[Any]:
    """Run ``coro`` as the session turn Task. Abort cancels this Task.

    The caller (event-bus handler) awaits this so the bus stays serial.
    ``CancelledError`` is swallowed so the bus consumer stays alive.
    """
    await cancel_active_turn(voice_session_id, reason="superseded")
    sess = voice_sessions.get(voice_session_id)
    if not isinstance(sess, dict):
        return await coro
    task = asyncio.create_task(coro)
    sess[TURN_TASK_KEY] = task
    try:
        return await task
    except asyncio.CancelledError:
        return None
    finally:
        if sess.get(TURN_TASK_KEY) is task:
            sess[TURN_TASK_KEY] = None
