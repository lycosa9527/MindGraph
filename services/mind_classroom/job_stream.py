"""SSE stream for Mind Classroom job progress (Redis push + Postgres reconcile)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Optional

from fastapi import HTTPException, Request, status
from fastapi.responses import StreamingResponse
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from repositories.mind_classroom_repo import MindClassroomJobRepository
from services.mind_classroom.job_events import (
    HEARTBEAT_SECONDS,
    MAX_SSE_CONNECTIONS_PER_USER,
    build_progress_payload,
    classroom_job_channel,
    classroom_sse_reconcile_payload,
    decode_pubsub_data,
    decrement_sse_connection,
    increment_sse_connection,
    sse_connection_count,
    sse_payload_is_terminal,
)
from services.mind_classroom.job_payload import job_event_dict
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.db.session_open import release_open_transaction

logger = logging.getLogger(__name__)

_PUBSUB_ERRORS = (RedisError, OSError, RuntimeError, ValueError, AttributeError)


async def _subscribe_job_pubsub(
    job_id: str,
    queue: asyncio.Queue[Optional[str]],
) -> tuple[Any, Optional[asyncio.Task[None]]]:
    """Subscribe to Redis live pushes. Returns (pubsub, reader) or (None, None)."""
    redis = get_async_redis()
    if redis is None:
        return None, None
    pubsub = redis.pubsub()

    async def _reader() -> None:
        try:
            async for message in pubsub.listen():
                if message is None or message.get("type") != "message":
                    continue
                text = decode_pubsub_data(message.get("data"))
                if text:
                    await queue.put(text)
        except _PUBSUB_ERRORS as exc:
            logger.debug("[MindClassroom] SSE pubsub reader stopped job=%s: %s", job_id, exc)
        finally:
            await queue.put(None)

    try:
        await pubsub.subscribe(classroom_job_channel(job_id))
    except _PUBSUB_ERRORS as exc:
        logger.debug("[MindClassroom] SSE subscribe failed job=%s: %s", job_id, exc)
        try:
            await pubsub.aclose()
        except _PUBSUB_ERRORS:
            pass
        return None, None
    reader_task = asyncio.create_task(_reader(), name=f"mind-classroom-sse-{job_id}")
    return pubsub, reader_task


async def _close_job_pubsub(
    reader_task: Optional[asyncio.Task[None]],
    pubsub: Any,
    job_id: str,
) -> None:
    """Cancel the Redis reader and drop the subscription."""
    if reader_task is not None:
        reader_task.cancel()
        try:
            await reader_task
        except asyncio.CancelledError:
            pass
        except _PUBSUB_ERRORS as exc:
            logger.debug("[MindClassroom] SSE reader join job=%s: %s", job_id, exc)
    if pubsub is None:
        return
    try:
        await pubsub.unsubscribe(classroom_job_channel(job_id))
        await pubsub.aclose()
    except _PUBSUB_ERRORS as exc:
        logger.debug("[MindClassroom] SSE pubsub close job=%s: %s", job_id, exc)


async def _next_sse_item(
    queue: asyncio.Queue[Optional[str]],
    use_queue: bool,
) -> tuple[Optional[str], bool]:
    """Wait for a Redis frame, or signal an idle tick. Second value is still-listening."""
    if not use_queue:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        return None, False
    try:
        item = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
    except TimeoutError:
        return None, True
    if item is None:
        return None, False
    return item, True


async def _iter_job_events(job_id: str, initial_payload: str) -> AsyncIterator[str]:
    """Yield SSE frames. Redis is the live push; Postgres is the idle reconcile."""
    yield ": stream_open\n\n"
    yield f"data: {initial_payload}\n\n"
    if sse_payload_is_terminal(initial_payload):
        return

    queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
    pubsub, reader_task = await _subscribe_job_pubsub(job_id, queue)
    use_queue = reader_task is not None
    try:
        while True:
            item, use_queue = await _next_sse_item(queue, use_queue)
            if item:
                yield f"data: {item}\n\n"
                if sse_payload_is_terminal(item):
                    return
                continue
            frame = await classroom_sse_reconcile_payload(job_id)
            yield f"data: {frame}\n\n"
            if sse_payload_is_terminal(frame):
                return
    finally:
        await _close_job_pubsub(reader_task, pubsub, job_id)


async def classroom_job_stream_response(
    request: Request,
    db: AsyncSession,
    job_id: str,
    current_user: User,
) -> StreamingResponse:
    """Return an SSE stream of progress events for one classroom job."""
    del request
    user_id = int(current_user.id)
    if sse_connection_count(user_id) >= MAX_SSE_CONNECTIONS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Maximum {MAX_SSE_CONNECTIONS_PER_USER} concurrent classroom streams allowed",
        )
    row = await MindClassroomJobRepository(db).get_by_uuid(job_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    initial_payload = build_progress_payload(job_event_dict(row))
    await release_open_transaction(db)

    increment_sse_connection(user_id)
    logger.debug(
        "[MindClassroom] SSE started job=%s user=%s connections=%s",
        job_id,
        user_id,
        sse_connection_count(user_id),
    )

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for chunk in _iter_job_events(job_id, initial_payload):
                yield chunk
        except asyncio.CancelledError:
            logger.debug("[MindClassroom] SSE cancelled job=%s user=%s", job_id, user_id)
            raise
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("[MindClassroom] SSE error job=%s: %s", job_id, exc)
            error_data = json.dumps({"type": "error", "error": "stream_unavailable"})
            yield f"data: {error_data}\n\n"
        finally:
            decrement_sse_connection(user_id)
            logger.debug(
                "[MindClassroom] SSE closed job=%s user=%s remaining=%s",
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
