"""Redis-backed LLM routing overrides shared across workers.

The hash ``llm:routing:overrides`` is the source of truth. Each worker copies
it into ``llm_routing_store`` and config properties read that copy.
"""

from __future__ import annotations

import logging
from typing import Dict, Mapping, Optional

from services.infrastructure.utils.llm_routing_store import (
    ALLOWED_FIELDS,
    normalize_updates,
    overrides_age_seconds,
    replace_overrides,
)
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

REDIS_KEY = "llm:routing:overrides"
REFRESH_SECONDS = 2.0


class RoutingStoreError(RuntimeError):
    """Redis could not persist or reload routing overrides."""


def _decode_hash(raw: Mapping[bytes | str, bytes | str]) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for key, value in raw.items():
        name = key.decode() if isinstance(key, bytes) else str(key)
        text = value.decode() if isinstance(value, bytes) else str(value)
        cleaned = text.strip()
        if name in ALLOWED_FIELDS and cleaned:
            parsed[name] = cleaned
    return parsed


async def refresh_routing_overrides(*, force: bool = False) -> bool:
    """Copy Redis overrides into this process. Failures keep the last copy."""
    if not force and overrides_age_seconds() < REFRESH_SECONDS:
        return True
    try:
        client = get_async_redis()
        raw = await client.hgetall(REDIS_KEY)
    except REDIS_ERRORS:
        logger.warning("LLM routing override refresh failed")
        return False
    if not isinstance(raw, dict):
        logger.warning("LLM routing override refresh returned a non-hash")
        return False
    replace_overrides(_decode_hash(raw))
    return True


async def apply_routing_updates(updates: Mapping[str, Optional[str]]) -> None:
    """Validate and write a partial override map, then refresh this process."""
    cleaned = normalize_updates(updates)
    try:
        client = get_async_redis()
        pipe = client.pipeline()
        for key, value in cleaned.items():
            if value is None:
                pipe.hdel(REDIS_KEY, key)
            else:
                pipe.hset(REDIS_KEY, key, value)
        await pipe.execute()
    except REDIS_ERRORS as exc:
        raise RoutingStoreError("redis_unavailable") from exc
    refreshed = await refresh_routing_overrides(force=True)
    if not refreshed:
        raise RoutingStoreError("redis_unavailable")
