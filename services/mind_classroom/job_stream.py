"""SSE stream for Mind Classroom job progress (Redis pub/sub + DB snapshot)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator, Optional

from fastapi import HTTPException, Request, status
from fastapi.responses import StreamingResponse
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from repositories.mind_classroom_repo import MindClassroomJobRepository
from services.mind_classroom.job_events import (
    HEARTBEAT_SECONDS,
    MAX_SSE_CONNECTIONS_PER_USER,
    TERMINAL_JOB_STATUSES,
    build_heartbeat_payload,
    build_progress_payload,
    classroom_job_channel,
    decode_pubsub_data,
    decrement_sse_connection,
    increment_sse_connection,
    sse_connection_count,
)
from services.mind_classroom.job_payload import job_event_dict
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.db.session_open import release_open_transaction

logger = logging.getLogger(__name__)


async def _iter_job_events(job_id: str, initial_payload: str) -> AsyncIterator[str]:
    """Yield SSE frames for one classroom job. Redis is required; no poll fallback."""
    yield ": stream_open\n\n"
    yield f"data: {initial_payload}\n\n"
    try:
        parsed = json.loads(initial_payload)
    except json.JSONDecodeError:
        parsed = {}
    job = parsed.get("job") if isinstance(parsed, dict) else None
    if isinstance(job, dict):
        status_value = job.get("status")
        if isinstance(status_value, str) and status_value in TERMINAL_JOB_STATUSES:
            return

    redis = get_async_redis()
    if redis is None:
        error_data = json.dumps({"type": "error", "error": "stream_unavailable"})
        yield f"data: {error_data}\n\n"
        return

    channel = classroom_job_channel(job_id)
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
            logger.debug("[MindClassroom] SSE pubsub reader stopped job=%s: %s", job_id, exc)
        finally:
            await queue.put(None)

    await pubsub.subscribe(channel)
    reader_task = asyncio.create_task(_reader(), name=f"mind-classroom-sse-{job_id}")
    terminal = False
    try:
        while not terminal:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
            except TimeoutError:
                yield f"data: {build_heartbeat_payload()}\n\n"
                continue
            if item is None:
                break
            yield f"data: {item}\n\n"
            try:
                parsed_item = json.loads(item)
            except json.JSONDecodeError:
                continue
            if parsed_item.get("type") == "progress":
                next_job = parsed_item.get("job") or {}
                status_value = next_job.get("status")
                if isinstance(status_value, str) and status_value in TERMINAL_JOB_STATUSES:
                    terminal = True
    finally:
        reader_task.cancel()
        try:
            await reader_task
        except asyncio.CancelledError:
            pass
        except (RedisError, OSError, RuntimeError, ValueError) as exc:
            logger.debug("[MindClassroom] SSE reader join job=%s: %s", job_id, exc)
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except (RedisError, OSError, RuntimeError, AttributeError) as exc:
            logger.debug("[MindClassroom] SSE pubsub close job=%s: %s", job_id, exc)


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
