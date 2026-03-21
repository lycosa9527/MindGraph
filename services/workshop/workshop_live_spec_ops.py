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

from config.database import SessionLocal
from models.domain.diagrams import Diagram
from services.redis.redis_client import get_redis
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


def ensure_live_spec_seeded(
    redis: Any,
    code: str,
    diagram_id: str,
    ttl_sec: int,
) -> Dict[str, Any]:
    """Load live spec from Redis or hydrate from ``Diagram.spec``."""
    existing = read_live_spec(redis, code)
    if existing:
        return existing
    db = SessionLocal()
    try:
        diagram = db.query(Diagram).filter(
            Diagram.id == diagram_id,
            ~Diagram.is_deleted,
        ).first()
        if not diagram:
            return {}
        return seed_live_spec_from_diagram(redis, code, diagram, ttl_sec)
    finally:
        db.close()


def mutate_live_spec_after_ws_update(
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
    current = ensure_live_spec_seeded(redis, code, diagram_id, ttl_sec)
    merged, _ver = apply_live_update(current, spec, nodes, connections)
    write_live_spec(redis, code, merged, ttl_sec)
    return merged


def maybe_flush_live_spec_when_room_empty(redis: Any, code: str) -> None:
    """After a participant leaves: if nobody remains, persist live Redis spec to Postgres."""
    try:
        remaining = redis.scard(participants_key(code))
    except (TypeError, AttributeError, RuntimeError):
        return
    if remaining != 0:
        return
    raw_did = redis.get(code_to_diagram_key(code))
    if not raw_did:
        return
    diagram_id_val = (
        raw_did if isinstance(raw_did, str) else raw_did.decode("utf-8")
    )
    flush_live_spec_to_db(code, diagram_id_val)


def flush_live_spec_to_db(code: str, diagram_id: str) -> bool:
    """Write Redis live spec to ``Diagram.spec``. Returns True if a row was updated."""
    redis = get_redis()
    if not redis:
        return False
    doc = read_live_spec(redis, code)
    if not doc:
        return False
    payload = spec_for_snapshot(doc)
    try:
        text = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):
        logger.warning("[LiveSpec] flush: JSON serialize failed for diagram %s", diagram_id)
        return False

    db = SessionLocal()
    try:
        diagram = db.query(Diagram).filter(
            Diagram.id == diagram_id,
            ~Diagram.is_deleted,
        ).first()
        if not diagram:
            return False
        diagram.spec = text
        db.commit()
        redis.set(live_last_db_flush_key(code), str(int(time.time())))
        logger.debug("[LiveSpec] Flushed diagram %s from workshop %s", diagram_id, code)
        return True
    except Exception as exc:
        logger.error("[LiveSpec] flush failed: %s", exc, exc_info=True)
        db.rollback()
        return False
    finally:
        db.close()
