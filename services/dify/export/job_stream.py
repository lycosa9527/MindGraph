"""
SSE stream for MindMate export job progress (Redis pub/sub + DB snapshot).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator, Optional

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.messages import Language, Messages
from services.dify.export.job_events import (
    HEARTBEAT_SECONDS,
    MAX_SSE_CONNECTIONS_PER_USER,
    TERMINAL_JOB_STATUSES,
    decode_pubsub_data,
    build_heartbeat_payload,
    decrement_sse_connection,
    export_job_channel,
    export_job_to_dict,
    increment_sse_connection,
    sse_connection_count,
)
from services.dify.export.job_storage import get_job
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)


async def _load_owned_job(
    db: AsyncSession,
    job_id: int,
    user_id: int,
    lang: Language,
):
    """Load a job owned by the requesting admin or raise 404."""
    job = await get_job(db, job_id)
    if job is None or int(job.created_by_user_id) != int(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("invalid_request", lang),
        )
    return job


async def _iter_job_events(job_id: int, initial_payload: str) -> AsyncIterator[str]:
    """Yield SSE frames for one export job."""
    yield ": stream_open\n\n"
    yield f"data: {initial_payload}\n\n"

    redis = get_async_redis()
    if redis is None:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            yield f"data: {build_heartbeat_payload()}\n\n"
        return

    channel = export_job_channel(job_id)
    pubsub = redis.pubsub()
    queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

    async def _reader() -> None:
        try:
            async for message in pubsub.listen():
                if message is None or message.get("type") != "message":
                    continue
                text = decode_pubsub_data(message.get("data"))
                if text:
                    await queue.put(text)
        except (RedisError, OSError, RuntimeError, ValueError) as exc:
            logger.debug("[MindMateExport] SSE pubsub reader stopped job=%s: %s", job_id, exc)
        finally:
            await queue.put(None)

    await pubsub.subscribe(channel)
    reader_task = asyncio.create_task(_reader(), name=f"mindmate-export-sse-{job_id}")
    terminal = False
    try:
        while not terminal:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                yield f"data: {build_heartbeat_payload()}\n\n"
                continue
            if item is None:
                break
            yield f"data: {item}\n\n"
            try:
                parsed = json.loads(item)
            except json.JSONDecodeError:
                continue
            if parsed.get("type") == "progress":
                job = parsed.get("job") or {}
                status_value = job.get("status")
                if isinstance(status_value, str) and status_value in TERMINAL_JOB_STATUSES:
                    terminal = True
    finally:
        reader_task.cancel()
        try:
            await reader_task
        except asyncio.CancelledError:
            pass
        except (RedisError, OSError, RuntimeError, ValueError) as exc:
            logger.debug("[MindMateExport] SSE reader join job=%s: %s", job_id, exc)
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except (RedisError, OSError, RuntimeError, AttributeError) as exc:
            logger.debug("[MindMateExport] SSE pubsub close job=%s: %s", job_id, exc)


async def mindmate_export_job_stream_response(
    db: AsyncSession,
    job_id: int,
    current_user: User,
    lang: Language,
) -> StreamingResponse:
    """Return an SSE stream of progress events for one export job."""
    user_id = int(current_user.id)
    if sse_connection_count(user_id) >= MAX_SSE_CONNECTIONS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Maximum {MAX_SSE_CONNECTIONS_PER_USER} concurrent export streams allowed",
        )

    job = await _load_owned_job(db, job_id, user_id, lang)
    initial_payload = json.dumps(
        {"type": "progress", "job": export_job_to_dict(job)},
        ensure_ascii=False,
    )

    increment_sse_connection(user_id)
    logger.debug(
        "[MindMateExport] SSE started job=%s user=%s connections=%s",
        job_id,
        user_id,
        sse_connection_count(user_id),
    )

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for chunk in _iter_job_events(job_id, initial_payload):
                yield chunk
        except asyncio.CancelledError:
            logger.debug("[MindMateExport] SSE cancelled job=%s user=%s", job_id, user_id)
            raise
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("[MindMateExport] SSE error job=%s: %s", job_id, exc)
            error_data = json.dumps({"type": "error", "error": "stream_unavailable"})
            yield f"data: {error_data}\n\n"
        finally:
            decrement_sse_connection(user_id)
            logger.debug(
                "[MindMateExport] SSE closed job=%s user=%s remaining=%s",
                job_id,
                user_id,
                sse_connection_count(user_id),
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
