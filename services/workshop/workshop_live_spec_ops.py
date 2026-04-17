"""
DB persistence and seeding for Redis live workshop spec (Phase 2).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

from sqlalchemy import select

from config.database import AsyncSessionLocal
from models.domain.diagrams import Diagram
from services.redis.redis_async_client import get_async_redis
from services.workshop.workshop_live_spec import (
    apply_live_update,
    read_live_spec,
    seed_live_spec_from_diagram,
    spec_for_snapshot,
    write_live_spec,
)
from services.workshop.workshop_redis_keys import (
    code_to_diagram_key,
    live_last_db_flush_key,
    participants_key,
)

logger = logging.getLogger(__name__)


async def ensure_live_spec_seeded(
    redis: Any,
    code: str,
    diagram_id: str,
    ttl_sec: int,
) -> Dict[str, Any]:
    """Load live spec from Redis or hydrate from ``Diagram.spec``."""
    existing = await read_live_spec(redis, code)
    if existing:
        return existing
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Diagram).filter(
                Diagram.id == diagram_id,
                ~Diagram.is_deleted,
            )
        )
        diagram = result.scalars().first()
        if not diagram:
            return {}
        return await seed_live_spec_from_diagram(redis, code, diagram, ttl_sec)


async def mutate_live_spec_after_ws_update(
    redis: Any,
    code: str,
    diagram_id: str,
    ttl_sec: int,
    spec: Optional[Any],
    nodes: Optional[Any],
    connections: Optional[Any],
) -> Optional[Dict[str, Any]]:
    """
    Merge one collab update into Redis. Returns the full live document (with ``v``).
    """
    current = await ensure_live_spec_seeded(redis, code, diagram_id, ttl_sec)
    merged, _ver = apply_live_update(current, spec, nodes, connections)
    await write_live_spec(redis, code, merged, ttl_sec)
    return merged


async def maybe_flush_live_spec_when_room_empty(redis: Any, code: str) -> None:
    """After a participant leaves: if nobody remains, persist live Redis spec to Postgres."""
    try:
        remaining = await redis.scard(participants_key(code))
    except (TypeError, AttributeError, RuntimeError):
        return
    if remaining != 0:
        return
    raw_did = await redis.get(code_to_diagram_key(code))
    if not raw_did:
        return
    diagram_id_val = raw_did if isinstance(raw_did, str) else raw_did.decode("utf-8")
    await flush_live_spec_to_db(code, diagram_id_val)


async def flush_live_spec_to_db(code: str, diagram_id: str) -> bool:
    """Write Redis live spec to ``Diagram.spec``. Returns True if a row was updated."""
    redis = get_async_redis()
    if not redis:
        return False
    doc = await read_live_spec(redis, code)
    if not doc:
        return False
    payload = spec_for_snapshot(doc)
    try:
        text = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):
        logger.warning("[LiveSpec] flush: JSON serialize failed for diagram %s", diagram_id)
        return False

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Diagram).filter(
                    Diagram.id == diagram_id,
                    ~Diagram.is_deleted,
                )
            )
            diagram = result.scalars().first()
            if not diagram:
                return False
            diagram.spec = text
            await db.commit()
            await redis.set(live_last_db_flush_key(code), str(int(time.time())))
            logger.debug("[LiveSpec] Flushed diagram %s from workshop %s", diagram_id, code)
            return True
        except Exception as exc:
            logger.error("[LiveSpec] flush failed: %s", exc, exc_info=True)
            await db.rollback()
            return False
