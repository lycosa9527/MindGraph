"""SSE stream for Showcase teaching-design cover ready/fail events."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncIterator, Optional

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.showcase import ShowcasePost
from services.redis.redis_async_client import get_async_redis
from services.showcase.covers.events import (
    COVER_SSE_MAX_SECONDS,
    HEARTBEAT_SECONDS,
    TERMINAL_EVENT_TYPES,
    build_cover_event_payload,
    build_heartbeat_payload,
    cover_event_channel,
    decode_pubsub_data,
)
from services.showcase.staff_permissions import can_view_non_approved_post
from services.showcase.storage import showcase_public_asset_url
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.db.session_open import release_open_transaction

logger = logging.getLogger(__name__)


async def _load_visible_post(
    db: AsyncSession,
    post_id: str,
    current_user: User,
) -> ShowcasePost:
    """Load a post the user may watch for cover updates."""
    result = await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if post.status == "approved":
        return post
    if not await can_view_non_approved_post(post, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return post


async def _iter_cover_events(
    post_id: str,
    initial_payload: Optional[str],
) -> AsyncIterator[str]:
    """Yield SSE frames until cover_ready/cover_fail or hard-stop timeout."""
    yield ": stream_open\n\n"
    if initial_payload:
        yield f"data: {initial_payload}\n\n"
        try:
            parsed = json.loads(initial_payload)
        except json.JSONDecodeError:
            parsed = {}
        if parsed.get("type") in TERMINAL_EVENT_TYPES:
            return

    redis = get_async_redis()
    if redis is None:
        deadline = time.monotonic() + COVER_SSE_MAX_SECONDS
        while time.monotonic() < deadline:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            yield f"data: {build_heartbeat_payload()}\n\n"
        fail = build_cover_event_payload(
            "cover_fail",
            post_id=post_id,
            reason="stream_unavailable",
        )
        yield f"data: {fail}\n\n"
        return

    channel = cover_event_channel(post_id)
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
            logger.debug(
                "[ShowcaseCover] SSE pubsub reader stopped post=%s: %s",
                post_id[:8],
                exc,
            )
        finally:
            await queue.put(None)

    await pubsub.subscribe(channel)
    reader_task = asyncio.create_task(_reader(), name=f"showcase-cover-sse-{post_id[:8]}")
    terminal = False
    deadline = time.monotonic() + COVER_SSE_MAX_SECONDS
    try:
        while not terminal and time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            wait = min(HEARTBEAT_SECONDS, max(0.1, remaining))
            try:
                item = await asyncio.wait_for(queue.get(), timeout=wait)
            except asyncio.TimeoutError:
                if time.monotonic() >= deadline:
                    break
                yield f"data: {build_heartbeat_payload()}\n\n"
                continue
            if item is None:
                break
            yield f"data: {item}\n\n"
            try:
                parsed = json.loads(item)
            except json.JSONDecodeError:
                continue
            if parsed.get("type") in TERMINAL_EVENT_TYPES:
                terminal = True
        if not terminal:
            fail = build_cover_event_payload(
                "cover_fail",
                post_id=post_id,
                reason="timeout",
            )
            yield f"data: {fail}\n\n"
    finally:
        reader_task.cancel()
        try:
            await reader_task
        except asyncio.CancelledError:
            pass
        except (RedisError, OSError, RuntimeError, ValueError) as exc:
            logger.debug(
                "[ShowcaseCover] SSE reader join post=%s: %s",
                post_id[:8],
                exc,
            )
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except (RedisError, OSError, RuntimeError, AttributeError) as exc:
            logger.debug(
                "[ShowcaseCover] SSE pubsub close post=%s: %s",
                post_id[:8],
                exc,
            )


async def showcase_cover_stream_response(
    db: AsyncSession,
    post_id: str,
    current_user: User,
) -> StreamingResponse:
    """Return an SSE stream of cover_ready / cover_fail for one post."""
    post = await _load_visible_post(db, post_id, current_user)
    initial_payload: Optional[str] = None
    if post.thumbnail_path:
        initial_payload = build_cover_event_payload(
            "cover_ready",
            post_id=post_id,
            thumbnail_url=showcase_public_asset_url(post.thumbnail_path),
        )
    await release_open_transaction(db)

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for chunk in _iter_cover_events(post_id, initial_payload):
                yield chunk
        except asyncio.CancelledError:
            logger.debug(
                "[ShowcaseCover] SSE cancelled post=%s user=%s",
                post_id[:8],
                current_user.id,
            )
            raise
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning(
                "[ShowcaseCover] SSE error post=%s: %s",
                post_id[:8],
                exc,
            )
            error_data = build_cover_event_payload(
                "cover_fail",
                post_id=post_id,
                reason="stream_unavailable",
            )
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
