"""Merge write and image Responses streams for node-explain research."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, Tuple

from agents.mind_maps.node_explain_prompts import RESEARCH_IMAGE_MAX
from services.infrastructure.http.error_handler import LLMServiceError
from services.llm.llm_utils import LLMUtils
from services.utils.error_types import LLM_PIPELINE_ERRORS

logger = logging.getLogger(__name__)

_IMAGE_FAILURES = (*LLM_PIPELINE_ERRORS, LLMServiceError)
_DONE = object()


def _keep_image_event(event: Dict[str, Any]) -> bool:
    kind = event.get("type")
    if kind == "image":
        return True
    return kind == "status" and event.get("phase") == "images"


def clip_research_images(
    event: Dict[str, Any],
    already: int,
    limit: int = RESEARCH_IMAGE_MAX,
) -> tuple[Dict[str, Any] | None, int]:
    """Keep at most ``limit`` images across the parallel image stream."""
    raw = event.get("images")
    if not isinstance(raw, list):
        return event, already
    room = limit - already
    if room <= 0:
        return None, already
    kept = raw[:room]
    nxt = already + len(kept)
    if len(kept) == len(raw):
        return event, nxt
    clipped = dict(event)
    clipped["images"] = kept
    return clipped, nxt


def split_image_events(event: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Yield one image card per event so the panel can paint them live."""
    raw = event.get("images")
    if not isinstance(raw, list) or len(raw) <= 1:
        return [event]
    return [{**event, "images": [image]} for image in raw]


async def merge_research_streams(
    write_events: AsyncGenerator[Dict[str, Any], None],
    image_events: AsyncGenerator[Dict[str, Any], None],
) -> AsyncGenerator[Dict[str, Any], None]:
    """Yield write events immediately; image cards arrive when ready."""
    queue: asyncio.Queue[Tuple[str, Any, bool]] = asyncio.Queue()

    async def _pump(
        stream: AsyncGenerator[Dict[str, Any], None],
        *,
        is_write: bool,
    ) -> None:
        try:
            async for item in stream:
                if is_write or _keep_image_event(item):
                    await queue.put(("item", item, is_write))
        except _IMAGE_FAILURES as exc:
            await queue.put(("error", exc, is_write))
        finally:
            await queue.put(("done", _DONE, is_write))

    tasks = [
        asyncio.create_task(_pump(write_events, is_write=True)),
        asyncio.create_task(_pump(image_events, is_write=False)),
    ]
    pending = 2
    image_kept = 0
    image_task = tasks[1]
    try:
        while pending:
            kind, payload, is_write = await queue.get()
            if kind == "done":
                pending -= 1
                continue
            if kind == "error":
                if is_write:
                    if isinstance(payload, Exception):
                        raise payload
                    raise LLMServiceError("Write research failed")
                if isinstance(payload, BaseException):
                    logger.warning(
                        "[NodeExplain] image research failed: %s",
                        LLMUtils.format_request_failure(payload),
                    )
                else:
                    logger.warning("[NodeExplain] image research failed")
                continue
            if not is_write and isinstance(payload, dict) and payload.get("type") == "image":
                clipped, image_kept = clip_research_images(payload, image_kept)
                if clipped is None:
                    if not image_task.done():
                        image_task.cancel()
                    continue
                for piece in split_image_events(clipped):
                    yield piece
                if image_kept >= RESEARCH_IMAGE_MAX and not image_task.done():
                    image_task.cancel()
                continue
            yield payload
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
