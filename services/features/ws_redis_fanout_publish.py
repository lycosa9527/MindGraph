"""
Redis publish helpers for WebSocket fan-out (PG NOTIFY fallback wrapper).

Re-exports core publish helpers and schedules PG NOTIFY when Redis publish fails.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict

from redis.exceptions import RedisError

from services.features.ws_pg_notify_fanout import publish_pg_notify_fanout_async
from services.features.ws_redis_fanout_publish_core import publish_chat_fanout_async as _publish_chat_fanout_core
from services.features.ws_redis_fanout_publish_core import (
    publish_workshop_fanout_async as _publish_workshop_fanout_core,
)
from services.features.ws_redis_fanout_publish_core import (
    _envelope_with_workshop_msg_id,
    stamp_chat_fanout_origin,
)
from services.infrastructure.monitoring.ws_metrics import record_ws_fanout_publish_failure
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)


async def publish_chat_fanout_async(envelope: Dict[str, Any]) -> None:
    """Publish chat fan-out; fall back to PG NOTIFY when Redis publish fails."""
    stamped = stamp_chat_fanout_origin(envelope)
    try:
        body = json.dumps(stamped, ensure_ascii=False)
    except (TypeError, ValueError):
        logger.warning("[WSFanout] Chat publish skipped: invalid envelope")
        return
    try:
        await _publish_chat_fanout_core(stamped)
    except RedisError:
        try:
            record_ws_fanout_publish_failure()
        except BACKGROUND_INFRA_ERRORS:
            pass
        asyncio.create_task(
            publish_pg_notify_fanout_async({"fanout": "chat", "payload": body}),
            name="ws-chat-fanout-pg-notify",
        )


async def publish_workshop_fanout_async(envelope: Dict[str, Any]) -> None:
    """Publish workshop fan-out; fall back to PG NOTIFY when Redis publish fails."""
    try:
        await _publish_workshop_fanout_core(envelope)
    except RedisError:
        try:
            record_ws_fanout_publish_failure()
        except BACKGROUND_INFRA_ERRORS:
            pass
        asyncio.create_task(
            publish_pg_notify_fanout_async(_envelope_with_workshop_msg_id(dict(envelope))),
            name="ws-fanout-pg-notify",
        )
