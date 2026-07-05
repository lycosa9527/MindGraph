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
from services.features.mindmate_collab.redis_keys import (
    closing_key,
    dify_stream_abort_key,
    dify_stream_lock_key,
    normalize_collab_code,
)
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


async def refresh_dify_stream_lock(code: str) -> None:
    """Extend the per-room Dify stream lock TTL during long upstream streams."""
    redis = get_async_redis()
    if not redis:
        return
    try:
        await redis.expire(
            dify_stream_lock_key(code),
            MINDMATE_COLLAB_DIFY_STREAM_TTL_SEC,
        )
    except REDIS_ERRORS:
        pass


async def release_dify_stream_lock(code: str) -> None:
    """Release the per-room Dify stream lock if held."""
    redis = get_async_redis()
    if not redis:
        return
    try:
        await redis.delete(dify_stream_lock_key(code))
    except REDIS_ERRORS:
        pass


def _marker_present(raw: object) -> bool:
    return raw is not None and raw not in (b"", "", b"0", "0")


async def signal_dify_stream_abort(code: str) -> None:
    """Set a cross-worker abort flag and cancel the local stream task if present."""
    redis = get_async_redis()
    if redis:
        try:
            await redis.set(
                dify_stream_abort_key(code),
                "1",
                ex=MINDMATE_COLLAB_DIFY_STREAM_TTL_SEC,
            )
        except REDIS_ERRORS:
            pass
    norm = normalize_collab_code(code)
    task = _active_tasks.get(norm)
    if task is not None and not task.done():
        task.cancel()


async def clear_dify_stream_abort(code: str) -> None:
    """Remove the cooperative abort marker after a stream finishes."""
    redis = get_async_redis()
    if not redis:
        return
    try:
        await redis.delete(dify_stream_abort_key(code))
    except REDIS_ERRORS:
        pass


async def is_dify_stream_aborted(code: str) -> bool:
    """Return True when the room stream should stop (abort flag or closing marker)."""
    redis = get_async_redis()
    if not redis:
        return False
    try:
        abort_raw = await redis.get(dify_stream_abort_key(code))
        if _marker_present(abort_raw):
            return True
        closing_raw = await redis.get(closing_key(code))
        return _marker_present(closing_raw)
    except REDIS_ERRORS:
        return False


async def abort_dify_stream(code: str) -> None:
    """Signal all workers to abort the in-flight Dify stream for this room."""
    await signal_dify_stream_abort(code)
