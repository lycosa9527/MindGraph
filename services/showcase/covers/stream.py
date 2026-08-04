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
from services.showcase.covers.enqueue import (
    enqueue_missing_office_preview,
    office_attachment_needs_preview,
)
from services.showcase.covers.events import (
    COVER_SSE_MAX_SECONDS,
    HEARTBEAT_SECONDS,
    TERMINAL_EVENT_TYPES,
    build_cover_event_payload,
    build_heartbeat_payload,
    cover_event_channel,
    decode_pubsub_data,
    get_cover_last_event,
)
from services.showcase.staff_permissions import can_view_non_approved_post
from services.showcase.storage import showcase_public_asset_url
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.db.rls_context import RlsContext, rls_async_session
from utils.db.session_open import release_open_transaction

logger = logging.getLogger(__name__)


def build_cover_ready_payload_from_post(post: ShowcasePost) -> Optional[str]:
    """Build cover_ready JSON when the post already has a usable cover/preview.

    Office attachments still missing ``preview_path`` return None so the stream
    waits for LibreOffice conversion instead of emitting a thumb-only ready.
    """
    if post.case_type == "teaching_design" and office_attachment_needs_preview(post.spec) is not None:
        return None
    if not post.thumbnail_path:
        return None
    preview_url = None
    if isinstance(post.spec, dict):
        preview_path = post.spec.get("preview_path")
        if isinstance(preview_path, str) and preview_path.strip():
            preview_url = showcase_public_asset_url(preview_path.lstrip("/"))
    return build_cover_event_payload(
        "cover_ready",
        post_id=str(post.id),
        thumbnail_url=showcase_public_asset_url(post.thumbnail_path),
        preview_url=preview_url,
    )


def select_terminal_cover_payload(
    *,
    post: Optional[ShowcasePost],
    last_event_payload: Optional[str],
) -> Optional[str]:
    """Choose a safe terminal SSE payload.

    DB ``cover_ready`` always wins. Redis last-event is only used for
    ``cover_fail`` when the DB is not ready yet — never replay a stale
    ``cover_ready`` while Office still lacks ``preview_path``.
    """
    if post is not None:
        ready = build_cover_ready_payload_from_post(post)
        if ready:
            return ready
    if not last_event_payload:
        return None
    try:
        parsed = json.loads(last_event_payload)
    except json.JSONDecodeError:
        return None
    if parsed.get("type") == "cover_fail":
        return last_event_payload
    return None


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


async def _reconcile_terminal_payload(
    post_id: str,
    *,
    user_id: int,
    organization_id: Optional[int],
) -> Optional[str]:
    """Return a terminal payload from fresh DB state, else validated last-event."""
    last = await get_cover_last_event(post_id)
    try:
        async with rls_async_session(RlsContext.for_celery_user(user_id, organization_id)) as db:
            result = await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))
            post = result.scalar_one_or_none()
            return select_terminal_cover_payload(post=post, last_event_payload=last)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.debug(
            "[ShowcaseCover] SSE DB reconcile failed post=%s: %s",
            post_id[:8],
            exc,
        )
        # Without DB, only honor cover_fail (never an unverified cover_ready).
        return select_terminal_cover_payload(post=None, last_event_payload=last)


async def _iter_cover_events(
    post_id: str,
    initial_payload: Optional[str],
    *,
    user_id: int,
    organization_id: Optional[int],
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

    # Catch publish-before-subscribe races (and late DB readiness).
    reconciled = await _reconcile_terminal_payload(
        post_id,
        user_id=user_id,
        organization_id=organization_id,
    )
    if reconciled:
        yield f"data: {reconciled}\n\n"
        return

    redis = get_async_redis()
    if redis is None:
        deadline = time.monotonic() + COVER_SSE_MAX_SECONDS
        while time.monotonic() < deadline:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            again = await _reconcile_terminal_payload(
                post_id,
                user_id=user_id,
                organization_id=organization_id,
            )
            if again:
                yield f"data: {again}\n\n"
                return
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
    # Re-check after subscribe so events published in the gap are not missed.
    reconciled = await _reconcile_terminal_payload(
        post_id,
        user_id=user_id,
        organization_id=organization_id,
    )
    if reconciled:
        yield f"data: {reconciled}\n\n"
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except (RedisError, OSError, RuntimeError, AttributeError):
            pass
        return

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
                again = await _reconcile_terminal_payload(
                    post_id,
                    user_id=user_id,
                    organization_id=organization_id,
                )
                if again:
                    yield f"data: {again}\n\n"
                    terminal = True
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
            # Final reconcile before declaring timeout.
            again = await _reconcile_terminal_payload(
                post_id,
                user_id=user_id,
                organization_id=organization_id,
            )
            if again:
                yield f"data: {again}\n\n"
            else:
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
    # Legacy Office posts may have a thumbnail but no LO preview.pdf — re-enqueue
    # and wait instead of emitting cover_ready with preview_url=null (PPTX spinner).
    needs_office_preview = (
        post.case_type == "teaching_design" and office_attachment_needs_preview(post.spec) is not None
    )
    if needs_office_preview:
        enqueue_missing_office_preview(
            post_id=post_id,
            case_type=post.case_type,
            spec=post.spec,
            author_id=int(post.author_id),
            organization_id=current_user.organization_id,
            actor_user_id=int(current_user.id),
        )
    # DB-ready wins; last-event cover_fail only when still not ready (after
    # enqueue clears stale terminals from prior attempts).
    initial_payload = select_terminal_cover_payload(
        post=post,
        last_event_payload=await get_cover_last_event(post_id),
    )
    await release_open_transaction(db)

    user_id = int(current_user.id)
    organization_id = current_user.organization_id

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for chunk in _iter_cover_events(
                post_id,
                initial_payload,
                user_id=user_id,
                organization_id=organization_id,
            ):
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
