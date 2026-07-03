"""Shared diagram library save helper for generation endpoints."""

from __future__ import annotations

import logging
from typing import Optional

from services.redis.cache.redis_diagram_cache import get_diagram_cache
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

SAVE_LIMIT_REACHED = "__SAVE_LIMIT_REACHED__"


async def try_save_diagram_to_library(
    user_id: Optional[int],
    *,
    title: str,
    diagram_type: str,
    spec: dict,
    language: str,
    organization_id: Optional[int] = None,
    http_request_id: Optional[str] = None,
    log_prefix: str = "diagram_save",
    source_channel: Optional[str] = None,
    conversation_id: Optional[str] = None,
    dify_user_key: Optional[str] = None,
) -> Optional[str]:
    """
    Save generated spec to the user's diagram library.

    Returns diagram id, SAVE_LIMIT_REACHED, or None on skip/failure. Never raises.
    """
    if user_id is None:
        return None
    safe_title = (title or "Diagram").strip()[:200] or "Diagram"
    dtype = (diagram_type or "mind_map").strip() or "mind_map"
    try:
        cache = get_diagram_cache()
        save_ok, new_id, save_err = await cache.save_diagram(
            user_id=user_id,
            diagram_id=None,
            title=safe_title,
            diagram_type=dtype,
            spec=spec,
            language=(language or "zh").strip() or "zh",
            thumbnail=None,
            organization_id=organization_id,
            source_channel=source_channel,
            conversation_id=conversation_id,
            dify_user_key=dify_user_key,
        )
        if save_ok and new_id:
            return str(new_id)
        if "limit reached" in (save_err or "").lower():
            logger.info(
                "%s: library full user=%s request_id=%s",
                log_prefix,
                user_id,
                http_request_id or "none",
            )
            return SAVE_LIMIT_REACHED
        logger.warning(
            "%s: library save failed user=%s request_id=%s: %s",
            log_prefix,
            user_id,
            http_request_id or "none",
            save_err,
        )
        return None
    except REDIS_ERRORS as save_exc:
        logger.warning(
            "%s: library save error user=%s request_id=%s: %s",
            log_prefix,
            user_id,
            http_request_id or "none",
            save_exc,
        )
        return None
