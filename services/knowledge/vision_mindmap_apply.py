"""Apply a vision-rebuilt mind map to the library + wake desktop Kitty."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services.kitty.infra.desktop.kitty_desktop_action_queue import (
    enqueue_kitty_desktop_action,
    mark_kitty_desktop_action_explicit_drain,
)
from services.kitty.infra.desktop.kitty_desktop_wake_fanout import (
    publish_kitty_desktop_action_pending,
)
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)


async def apply_rebuilt_mindmap_to_library(
    *,
    user_id: int,
    diagram_id: str,
    spec: Dict[str, Any],
    language: str,
    title: Optional[str] = None,
    organization_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Replace library diagram spec and enqueue desktop reload action.

    Returns a small status dict: ``{saved, desktop_queued}``.
    """
    diagram_id = (diagram_id or "").strip()
    if not diagram_id:
        return {"saved": False, "desktop_queued": False, "error": "missing_diagram_id"}

    cache = get_diagram_cache()
    existing_title = (title or "").strip()
    if not existing_title:
        try:
            existing = await cache.get_diagram(user_id, diagram_id)
        except REDIS_ERRORS:
            existing = None
        if isinstance(existing, dict):
            existing_title = str(existing.get("title") or "").strip()
    if not existing_title:
        existing_title = "Mind Map"

    save_ok, saved_id, save_err = await cache.save_diagram(
        user_id=user_id,
        diagram_id=diagram_id,
        title=existing_title[:200],
        diagram_type="mind_map",
        spec=spec,
        language=language or "zh",
        thumbnail=None,
        organization_id=organization_id,
    )
    if not save_ok:
        logger.warning(
            "[VisionMindmap] library save failed user=%s diagram=%s: %s",
            user_id,
            diagram_id,
            save_err,
        )
        return {"saved": False, "desktop_queued": False, "error": save_err or "save_failed"}

    payload = {
        "kind": "reload_library_diagram",
        "diagram_library_id": saved_id or diagram_id,
        "title": existing_title[:256],
    }
    queued = False
    try:
        queued = await enqueue_kitty_desktop_action(user_id, payload)
        if queued:
            await mark_kitty_desktop_action_explicit_drain(user_id)
            await publish_kitty_desktop_action_pending(user_id)
    except REDIS_ERRORS as exc:
        logger.warning(
            "[VisionMindmap] desktop enqueue failed user=%s diagram=%s: %s",
            user_id,
            diagram_id,
            exc,
        )
        queued = False

    return {
        "saved": True,
        "desktop_queued": bool(queued),
        "diagram_id": saved_id or diagram_id,
    }
