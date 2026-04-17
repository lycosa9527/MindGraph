"""
Redis Diagram Cache Helpers
============================

Helper functions, constants, and database utilities for RedisDiagramCache.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
from typing import Any, List, Tuple

from sqlalchemy import select
from sqlalchemy.sql.functions import count as sa_count

from config.database import AsyncSessionLocal
from models.domain.diagrams import Diagram
from services.redis import keys as _keys

logger = logging.getLogger(__name__)

CACHE_TTL = _keys.TTL_DIAGRAM
SYNC_INTERVAL = float(os.getenv("DIAGRAM_SYNC_INTERVAL", "300"))
SYNC_BATCH_SIZE = int(os.getenv("DIAGRAM_SYNC_BATCH_SIZE", "100"))
MAX_PER_USER = int(os.getenv("DIAGRAM_MAX_PER_USER", "20"))
MAX_SPEC_SIZE_KB = int(os.getenv("DIAGRAM_MAX_SPEC_SIZE_KB", "500"))

DIAGRAM_KEY = _keys.DIAGRAM
USER_META_KEY = _keys.DIAGRAMS_USER_META
USER_LIST_KEY = _keys.DIAGRAMS_USER_LIST


async def _redis_json_set_paths(
    redis_client: Any,
    key: str,
    path_value_pairs: List[Tuple[str, Any]],
    ttl: int,
) -> bool:
    """
    Update one or more JSON paths in-place in a single pipeline.

    All JSON.SET commands and the EXPIRE are sent together.
    Returns True on success, False if any Redis command raises an error
    (e.g. key does not exist, RedisJSON not loaded, connection failure).
    """
    try:
        async with redis_client.pipeline(transaction=False) as pipe:
            for path, value in path_value_pairs:
                pipe.json().set(key, path, value)
            pipe.expire(key, ttl)
            await pipe.execute()
        return True
    except Exception as exc:
        logger.debug("[DiagramCache] JSON.SET paths failed for %s: %s", key, exc)
        return False


async def count_diagrams_from_db(user_id: int) -> int:
    """Count non-deleted diagrams for a user directly from the database."""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(sa_count()).select_from(Diagram).where(Diagram.user_id == user_id, Diagram.is_deleted.is_(False))
            )
            return result.scalar_one()
    except Exception as exc:
        logger.error("[DiagramCache] Database count failed: %s", exc)
        return 0
