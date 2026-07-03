"""
Dify stream lock and in-flight task control for MindMate collab.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
from typing import Dict

from services.features.mindmate_collab.config import MINDMATE_COLLAB_DIFY_STREAM_TTL_SEC
from services.features.mindmate_collab.redis_keys import dify_stream_lock_key, normalize_collab_code
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS

_active_tasks: Dict[str, asyncio.Task] = {}


def register_dify_stream_task(code: str, task: asyncio.Task) -> None:
    """Track a background Dify stream task for abort-on-teardown."""
    _active_tasks[normalize_collab_code(code)] = task


def clear_dify_stream_task(code: str) -> None:
    """Drop task tracking when a stream finishes."""
    _active_tasks.pop(normalize_collab_code(code), None)


async def acquire_dify_stream_lock(code: str) -> bool:
    """Return True when this caller holds the per-room Dify stream lock."""
    redis = get_async_redis()
    if not redis:
        return False
    try:
        ok = await redis.set(
            dify_stream_lock_key(code),
            "1",
            nx=True,
            ex=MINDMATE_COLLAB_DIFY_STREAM_TTL_SEC,
        )
        return bool(ok)
    except REDIS_ERRORS:
        return False


async def release_dify_stream_lock(code: str) -> None:
    """Release the per-room Dify stream lock if held."""
    redis = get_async_redis()
    if not redis:
        return
    try:
        await redis.delete(dify_stream_lock_key(code))
    except REDIS_ERRORS:
        pass


async def abort_dify_stream(code: str) -> None:
    """Cancel an in-flight Dify stream and release its lock."""
    norm = normalize_collab_code(code)
    task = _active_tasks.pop(norm, None)
    if task and not task.done():
        task.cancel()
    await release_dify_stream_lock(code)
