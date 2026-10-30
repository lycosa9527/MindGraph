"""Copy Postgres-owned seminar fields onto the live Redis hash.

The hash is a cache of a live row. A missing hash is left missing so this
write cannot publish a partial room. The next connect republishes the full
row from Postgres.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Mapping

from services.features.mindmate_seminar.redis_keys import normalize_collab_code, session_meta_key
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS
from services.utils.typing_helpers import redis_hset_mapping

logger = logging.getLogger(__name__)


async def mirror_live_session_fields(code: str, fields: Mapping[str, str]) -> None:
    """Update an existing live room hash. No-op when Redis has no full room."""
    if not code.strip() or not fields:
        return
    redis = get_async_redis()
    if not redis:
        return
    norm = normalize_collab_code(code)
    meta_key = session_meta_key(norm)
    try:
        if not await redis.hexists(meta_key, "session_id"):
            return
        await redis.hset(meta_key, mapping=redis_hset_mapping(dict(fields)))
    except REDIS_ERRORS as exc:
        logger.warning("[MindmateSeminar] live hash mirror failed code=%s: %s", norm, exc)
