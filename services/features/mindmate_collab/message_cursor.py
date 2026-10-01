"""
Latest saved seminar line, so a live socket can notice a missed fan-out.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from services.features.mindmate_collab.redis_keys import normalize_collab_code, session_meta_key
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

LATEST_MESSAGE_ID_FIELD = "latest_message_id"


def parse_latest_message_id(raw: Any) -> Optional[int]:
    """Parse a Redis latest-line value. Non-positive and junk values are absent."""
    if raw is None or isinstance(raw, bool):
        return None
    text: str
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
    elif isinstance(raw, str):
        text = raw
    else:
        text = str(raw)
    try:
        value = int(text)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return value


async def remember_latest_collab_message_id(code: str, message_id: int) -> None:
    """Record the newest saved line for this room. Fan-out remains the live path."""
    if message_id <= 0 or not code.strip():
        return
    redis = get_async_redis()
    if not redis:
        return
    try:
        await redis.hset(
            session_meta_key(normalize_collab_code(code)),
            LATEST_MESSAGE_ID_FIELD,
            str(message_id),
        )
    except REDIS_ERRORS as exc:
        logger.debug(
            "[MindmateCollab] latest message id was not stored code=%s: %s",
            normalize_collab_code(code),
            exc,
        )


async def read_latest_collab_message_id(code: str) -> Optional[int]:
    """Return the newest saved line id, or None when Redis has no cursor."""
    if not code.strip():
        return None
    redis = get_async_redis()
    if not redis:
        return None
    try:
        raw = await redis.hget(
            session_meta_key(normalize_collab_code(code)),
            LATEST_MESSAGE_ID_FIELD,
        )
    except REDIS_ERRORS as exc:
        logger.debug(
            "[MindmateCollab] latest message id was not read code=%s: %s",
            normalize_collab_code(code),
            exc,
        )
        return None
    return parse_latest_message_id(raw)
