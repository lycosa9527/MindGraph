"""Educational research dimensions for MindBot (chat scope, modality, dialogue depth)."""

from __future__ import annotations

from typing import Any, Optional

from services.mindbot.core.redis_keys import TURN_COUNT_PREFIX, TURN_COUNT_TTL_SECONDS
from services.mindbot.redis_async import redis_incr_with_ttl
from utils.env_helpers import env_bool


def education_metrics_enabled() -> bool:
    """Per-thread user-turn index and related Redis-backed fields."""
    return env_bool("MINDBOT_EDUCATION_METRICS", True)


def dingtalk_chat_scope(body: dict[str, Any]) -> str:
    """
    Return ``group`` (group chat), ``oto`` (one-to-one), or ``unknown``.

    DingTalk ``conversationType`` / ``conversation_type`` is often ``2`` or ``group``
    for groups; other values are treated as one-to-one.
    """
    ct = body.get("conversationType") or body.get("conversation_type")
    if ct is None:
        return "unknown"
    s = str(ct).strip().lower()
    if s in ("2", "group"):
        return "group"
    return "oto"


async def conversation_user_turn_index(
    organization_id: int,
    conversation_id_dt: str,
) -> Optional[int]:
    """
    Monotonic user-message index within a DingTalk thread (Redis INCR).

    Used for engagement / dialogue-depth research (e.g. follow-up questions).
    Returns ``None`` if Redis is unavailable, metrics are disabled, or the
    conversation id is empty.
    """
    if not education_metrics_enabled():
        return None
    if not conversation_id_dt.strip():
        return None
    key = f"{TURN_COUNT_PREFIX}{organization_id}:{conversation_id_dt}"
    return await redis_incr_with_ttl(key, TURN_COUNT_TTL_SECONDS)
