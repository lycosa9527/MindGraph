"""
Redis publish helpers for WebSocket fan-out (no subscription / listener).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from services.features.ws_redis_fanout_config import (
    CHAT_FANOUT_CHANNEL,
    WORKSHOP_FANOUT_CHANNEL,
    is_ws_fanout_enabled,
)
from services.infrastructure.monitoring.ws_metrics import (
    record_ws_fanout_chat_published,
    record_ws_fanout_workshop_published,
)
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)


async def publish_chat_fanout_async(envelope: Dict[str, Any]) -> None:
    """Publish a chat fan-out envelope using the native async Redis client."""
    if not is_ws_fanout_enabled():
        return
    try:
        body = json.dumps(envelope, ensure_ascii=False)
    except (TypeError, ValueError):
        logger.warning("[WSFanout] Chat publish skipped: invalid envelope")
        return
    client = get_async_redis()
    if not client:
        return
    try:
        record_ws_fanout_chat_published()
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("[WSFanout] chat publish metric failed: %s", exc)
    await client.publish(CHAT_FANOUT_CHANNEL, body)


async def publish_workshop_fanout_async(envelope: Dict[str, Any]) -> None:
    """Publish a workshop fan-out envelope using the native async Redis client."""
    if not is_ws_fanout_enabled():
        return
    try:
        body = json.dumps(envelope, ensure_ascii=False)
    except (TypeError, ValueError):
        logger.warning("[WSFanout] Workshop publish skipped: invalid envelope")
        return
    client = get_async_redis()
    if not client:
        return
    try:
        record_ws_fanout_workshop_published()
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("[WSFanout] workshop publish metric failed: %s", exc)
    await client.publish(WORKSHOP_FANOUT_CHANNEL, body)
