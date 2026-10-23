"""
Redis Diagram Cache Helpers
============================

Helper functions, constants, and database utilities for RedisDiagramCache.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import json
import logging
import os
from typing import Any, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.sql.functions import count as sa_count

from models.domain.diagrams import Diagram
from services.redis import keys as _keys
from services.utils.error_types import REDIS_ERRORS
from utils.db.session_open import user_rls_session

logger = logging.getLogger(__name__)

CACHE_TTL = _keys.TTL_DIAGRAM
SYNC_INTERVAL = float(os.getenv("DIAGRAM_SYNC_INTERVAL", "300"))
SYNC_BATCH_SIZE = int(os.getenv("DIAGRAM_SYNC_BATCH_SIZE", "100"))
# Legacy env default; per-user save caps are tier-based (see utils.auth.school_tier).
MAX_PER_USER = int(os.getenv("DIAGRAM_MAX_PER_USER", "20"))
MAX_SPEC_SIZE_KB = int(os.getenv("DIAGRAM_MAX_SPEC_SIZE_KB", "500"))
# Canvas body stays at MAX_SPEC_SIZE_KB. Extra model diagrams share this
# ceiling. The slot count follows however many models succeeded. Must match
# the frontend.
MAX_SPEC_WITH_LLM_RESULTS_KB = int(os.getenv("DIAGRAM_MAX_SPEC_WITH_LLM_RESULTS_KB", "4000"))


def diagram_spec_size_error(spec: dict[str, Any], spec_json: str) -> Optional[str]:
    """Reject a canvas over 500KB. Specs that store model diagrams use 4000KB."""
    size_kb = len(spec_json.encode("utf-8")) / 1024
    llm_results = spec.get("llm_results")
    if isinstance(llm_results, dict):
        canvas = {key: value for key, value in spec.items() if key != "llm_results"}
        canvas_kb = len(json.dumps(canvas).encode("utf-8")) / 1024
        if canvas_kb > MAX_SPEC_SIZE_KB:
            return f"Diagram spec too large ({canvas_kb:.1f}KB > {MAX_SPEC_SIZE_KB}KB)"
        if size_kb > MAX_SPEC_WITH_LLM_RESULTS_KB:
            return f"Diagram spec too large ({size_kb:.1f}KB > {MAX_SPEC_WITH_LLM_RESULTS_KB}KB)"
        return None
    if size_kb > MAX_SPEC_SIZE_KB:
        return f"Diagram spec too large ({size_kb:.1f}KB > {MAX_SPEC_SIZE_KB}KB)"
    return None


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
    except REDIS_ERRORS as exc:
        logger.debug("[DiagramCache] JSON.SET paths failed for %s: %s", key, exc)
        return False


async def count_diagrams_from_db(
    user_id: int,
    organization_id: Optional[int] = None,
) -> int:
    """Count non-deleted diagrams for a user directly from the database."""
    try:
        async with user_rls_session(user_id, organization_id) as db:
            result = await db.execute(
                select(sa_count()).select_from(Diagram).where(Diagram.user_id == user_id, Diagram.is_deleted.is_(False))
            )
            return result.scalar_one()
    except REDIS_ERRORS as exc:
        logger.error("[DiagramCache] Database count failed: %s", exc)
        return 0
