"""In-process concurrent MindMate (``/api/ai_assistant/stream``) Dify SSE streams.

Each open streaming response body increments the counter; ``finally`` decrements
so the admin payload can report live cluster load (per-worker values merged with
a sum, same pattern as MindBot).

Copyright 2024-2026 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class _MindmateStreamState:
    """Serialize counter updates with the async generator that handles each SSE run."""

    __slots__ = ("_lock", "_n")

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._n = 0

    async def begin(self) -> None:
        async with self._lock:
            self._n += 1

    async def end(self) -> None:
        try:
            async with self._lock:
                if self._n > 0:
                    self._n -= 1
        except (RuntimeError, TypeError) as exc:
            logger.debug("mindmate stream end: %s", exc)

    async def snapshot(self) -> Dict[str, Any]:
        async with self._lock:
            return {"active_mindmate_streaming": int(self._n)}


_STATE = _MindmateStreamState()


async def mindmate_streaming_begin() -> None:
    """Call when a MindMate Dify stream starts (at ``generate()`` entry)."""

    await _STATE.begin()


async def mindmate_streaming_end() -> None:
    """Call in ``finally`` when a MindMate stream ends."""

    await _STATE.end()


async def mindmate_streaming_snapshot() -> Dict[str, Any]:
    """Per-worker count for the admin performance worker snapshot."""

    try:
        return await _STATE.snapshot()
    except (RuntimeError, TypeError) as exc:
        return {"error": str(exc)}
