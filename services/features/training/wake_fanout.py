"""Redis pub/sub when a training session snapshot changes.

One PUBLISH per event. Workers pattern-subscribe; idle users generate no traffic.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from services.features.training.constants import (
    SNAPSHOT_TYPE,
    WAKE_ORG_CHANNEL,
    WAKE_USER_CHANNEL,
)
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)


def training_snapshot_frame(view: Dict[str, Any]) -> str:
    """JSON body that tells the watch to paint the HUD."""
    body = dict(view)
    body["type"] = SNAPSHOT_TYPE
    return json.dumps(body, ensure_ascii=False)


def training_user_wake_channel(user_id: int) -> str:
    """Per-account Redis pub/sub channel for training-remote sockets."""
    return WAKE_USER_CHANNEL.format(user_id=int(user_id))


def training_org_wake_channel(org_id: int) -> str:
    """Per-org Redis pub/sub channel for training-remote sockets."""
    return WAKE_ORG_CHANNEL.format(org_id=int(org_id))


def user_id_from_wake_channel(channel: str) -> Optional[int]:
    """Parse ``training_remote:user:{id}:wake``. Invalid channels return None."""
    parts = channel.split(":")
    if len(parts) != 4:
        return None
    if parts[0] != "training_remote" or parts[1] != "user" or parts[3] != "wake":
        return None
    try:
        return int(parts[2])
    except ValueError:
        return None


def org_id_from_wake_channel(channel: str) -> Optional[int]:
    """Parse ``training_remote:org:{id}:wake``. Invalid channels return None."""
    parts = channel.split(":")
    if len(parts) != 4:
        return None
    if parts[0] != "training_remote" or parts[1] != "org" or parts[3] != "wake":
        return None
    try:
        return int(parts[2])
    except ValueError:
        return None


async def publish_training_wake_json(channel: str, payload: str) -> None:
    """Fan out one frame to every worker that holds a training-remote socket."""
    redis = get_async_redis()
    if redis is None:
        return
    try:
        await redis.publish(channel, payload)
    except REDIS_ERRORS as exc:
        logger.debug("[TrainingRemote] wake publish failed: %s", exc)


async def publish_training_snapshot_view(
    org_id: int,
    view: Dict[str, Any],
    *,
    instructor_id: Optional[int] = None,
) -> None:
    """Push a HUD snapshot to the instructor and any org listeners."""
    payload = training_snapshot_frame(view)
    if instructor_id is not None and int(instructor_id) > 0:
        await publish_training_wake_json(training_user_wake_channel(int(instructor_id)), payload)
    if int(org_id) > 0:
        await publish_training_wake_json(training_org_wake_channel(int(org_id)), payload)
