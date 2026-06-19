"""Link active MindMate / MindBot Dify sessions to MindGraph users for library save.

When MindGraph starts a Dify chat it already knows the caller. ``/api/generate_dingtalk``
is invoked later by Dify's HTTP tool without browser cookies, so the tool should pass
``conversation_id`` (``{{sys.conversation_id}}``) and/or the Dify ``user`` string.
This registry bridges those keys back to the user recorded at session start.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from redis.exceptions import RedisError

from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

SESSION_PREFIX = "mg:gen_session:"
SESSION_TTL_SECONDS = 600


def _conv_key(conversation_id: str) -> str:
    return f"{SESSION_PREFIX}conv:{conversation_id.strip()[:100]}"


def _dify_key(dify_user_id: str) -> str:
    return f"{SESSION_PREFIX}dify:{dify_user_id.strip()[:256]}"


def _parse_payload(raw: str) -> Optional[dict[str, Any]]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    dify_user = data.get("dify_user_id")
    if not isinstance(dify_user, str) or not dify_user.strip():
        return None
    org_raw = data.get("organization_id")
    org_id = int(org_raw) if org_raw is not None else None
    user_raw = data.get("user_id")
    user_id = int(user_raw) if isinstance(user_raw, int) and user_raw > 0 else None
    registered_at = data.get("registered_at")
    ts = float(registered_at) if isinstance(registered_at, (int, float)) else None
    channel = data.get("channel")
    return {
        "user_id": user_id,
        "organization_id": org_id,
        "dify_user_id": dify_user.strip()[:256],
        "channel": channel if isinstance(channel, str) else "",
        "registered_at": ts,
    }


async def register_generation_session(
    *,
    channel: str,
    dify_user_id: str,
    organization_id: Optional[int],
    conversation_id: Optional[str],
    user_id: Optional[int] = None,
) -> bool:
    """
    Record caller identity when MindGraph opens a Dify MindMate or MindBot session.

    ``user_id`` is set for authenticated web MindMate; MindBot may omit it and rely on
    ``dify_user_id`` (``mindbot_{org}_{staff}``) plus the DingTalk bind table at save time.
    """
    dify_clean = (dify_user_id or "").strip()
    if not dify_clean:
        return False
    redis = get_async_redis()
    if redis is None:
        return False
    payload = json.dumps(
        {
            "channel": (channel or "").strip()[:32],
            "dify_user_id": dify_clean[:256],
            "organization_id": organization_id,
            "user_id": user_id if user_id is not None and user_id > 0 else None,
            "registered_at": time.time(),
        },
        separators=(",", ":"),
    )
    keys = [_dify_key(dify_clean)]
    conv_clean = (conversation_id or "").strip()
    if conv_clean:
        keys.append(_conv_key(conv_clean))
    try:
        for key in keys:
            await redis.set(key, payload, ex=SESSION_TTL_SECONDS)
        return True
    except RedisError as exc:
        logger.warning(
            "[GenSession] register failed channel=%s dify=%s: %s",
            channel,
            dify_clean[:32],
            exc,
        )
        return False


async def _fetch(redis: Any, key: str) -> Optional[dict[str, Any]]:
    try:
        raw = await redis.get(key)
    except RedisError as exc:
        logger.warning("[GenSession] lookup failed key=%s: %s", key, exc)
        return None
    if not isinstance(raw, str) or not raw.strip():
        return None
    return _parse_payload(raw)


async def lookup_generation_session(
    *,
    conversation_id: Optional[str] = None,
    dify_user_key: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Resolve a session recorded at MindMate / MindBot stream start.

    Priority: explicit ``conversation_id``, then explicit ``dify_user_key``.
    """
    redis = get_async_redis()
    if redis is None:
        return None

    conv_clean = (conversation_id or "").strip()
    if conv_clean:
        ctx = await _fetch(redis, _conv_key(conv_clean))
        if ctx is not None:
            return ctx

    dify_clean = (dify_user_key or "").strip()
    if dify_clean:
        ctx = await _fetch(redis, _dify_key(dify_clean))
        if ctx is not None:
            return ctx

    return None
