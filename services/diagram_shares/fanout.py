"""
Redis pub/sub so shared-diagram spec snapshots reach every app worker.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from services.diagram_shares.rooms import relay_share_spec
from services.features.ws_redis_fanout_config import is_ws_fanout_enabled
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import JSON_PARSE_ERRORS, REDIS_ERRORS

logger = logging.getLogger(__name__)

SHARE_FANOUT_CHANNEL = "mg:ws:diagram-share"


def _origin_secret() -> str:
    return os.getenv("COLLAB_FANOUT_ORIGIN_SECRET", "")


def build_share_fanout_body(diagram_id: str, from_tab: str, body: str) -> str:
    """Envelope published on ``SHARE_FANOUT_CHANNEL``."""
    envelope: dict[str, str] = {
        "diagram_id": diagram_id,
        "from_tab": from_tab,
        "body": body,
    }
    secret = _origin_secret()
    if secret:
        envelope["origin"] = secret
    return json.dumps(envelope)


def parse_share_fanout_body(raw: str) -> Optional[tuple[str, str, str]]:
    """Return ``(diagram_id, from_tab, body)`` or None when the envelope is unusable."""
    try:
        payload = json.loads(raw)
    except JSON_PARSE_ERRORS:
        return None
    if not isinstance(payload, dict):
        return None
    secret = _origin_secret()
    if secret and payload.get("origin") != secret:
        logger.warning("[DiagramShare] rejected fan-out envelope with invalid origin")
        return None
    diagram_id = payload.get("diagram_id")
    from_tab = payload.get("from_tab")
    body = payload.get("body")
    if not isinstance(diagram_id, str) or not diagram_id:
        return None
    if not isinstance(from_tab, str) or not from_tab:
        return None
    if not isinstance(body, str) or not body:
        return None
    return diagram_id, from_tab, body


async def publish_share_spec(diagram_id: str, from_tab: str, body: str) -> None:
    """Deliver a spec snapshot on this worker, and to other workers when fan-out is on."""
    if not is_ws_fanout_enabled():
        await relay_share_spec(diagram_id, from_tab, body)
        return
    redis = get_async_redis()
    if redis is None:
        await relay_share_spec(diagram_id, from_tab, body)
        return
    try:
        envelope = build_share_fanout_body(diagram_id, from_tab, body)
        await redis.publish(SHARE_FANOUT_CHANNEL, envelope)
    except REDIS_ERRORS as exc:
        logger.warning("[DiagramShare] fan-out publish failed diagram=%s: %s", diagram_id, exc)
        await relay_share_spec(diagram_id, from_tab, body)
