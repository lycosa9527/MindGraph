"""Redis pub/sub when a 演讲模式 click is queued or the HUD changes.

One PUBLISH per event. Workers pattern-subscribe; idle users generate no traffic.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from services.features.slides_remote.constants import (
    COMMAND_PENDING_TYPE,
    SNAPSHOT_TYPE,
    WAKE_CHANNEL,
)
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)


def slides_command_pending_payload() -> str:
    """JSON body that tells desktop to LPOP ``GET /commands``."""
    return json.dumps({"type": COMMAND_PENDING_TYPE}, ensure_ascii=False)


def slides_snapshot_frame(view: Dict[str, Any]) -> str:
    """JSON body that tells the watch to paint the HUD."""
    body = dict(view)
    body["type"] = SNAPSHOT_TYPE
    return json.dumps(body, ensure_ascii=False)


def slides_wake_channel(user_id: int) -> str:
    """Per-account Redis pub/sub channel for slides-remote sockets."""
    return WAKE_CHANNEL.format(user_id=int(user_id))


def user_id_from_wake_channel(channel: str) -> Optional[int]:
    """Parse ``slide_remote:user:{id}:wake``. Invalid channels return None."""
    parts = channel.split(":")
    if len(parts) != 4:
        return None
    if parts[0] != "slide_remote" or parts[1] != "user" or parts[3] != "wake":
        return None
    try:
        return int(parts[2])
    except ValueError:
        return None


async def publish_slides_wake_json(user_id: int, payload: str) -> None:
    """Fan out one frame to every worker that holds a slides-remote socket."""
    redis = get_async_redis()
    if redis is None:
        return
    try:
        await redis.publish(slides_wake_channel(user_id), payload)
    except REDIS_ERRORS as exc:
        logger.debug("[SlideRemote] wake publish failed user=%s: %s", user_id, exc)


async def publish_slides_command_pending(user_id: int) -> None:
    """Wake desktop sockets so they can drain queued clicks."""
    await publish_slides_wake_json(user_id, slides_command_pending_payload())


async def publish_slides_snapshot_view(user_id: int, view: Dict[str, Any]) -> None:
    """Push a HUD snapshot to watch sockets (and any other listeners)."""
    await publish_slides_wake_json(user_id, slides_snapshot_frame(view))
