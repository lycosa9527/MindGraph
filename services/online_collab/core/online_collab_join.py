"""Join/status entry points delegated from ``OnlineCollabManager``."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from config.database import AsyncSessionLocal
from models.domain.diagrams import Diagram
from services.online_collab.lifecycle.online_collab_expiry import (
    is_online_collab_expired,
)
from services.online_collab.lifecycle.online_collab_session_fields import (
    backfill_online_collab_expiry_if_needed,
)
from services.online_collab.lifecycle.online_collab_visibility_helpers import (
    ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
    diagram_online_collab_visibility,
    user_may_join_diagram_online_collab,
)
from services.online_collab.redis.online_collab_redis_keys import (
    code_to_diagram_key,
)
from services.online_collab.lifecycle.online_collab_join_helpers import (
    restore_online_collab_redis_from_db_row,
)
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)


async def get_active_online_collab_code_for_diagram_impl(
    diagram_id: str,
) -> Optional[str]:
    """Return active non-expired workshop code for diagram, else None."""
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(
                    Diagram.workshop_code,
                    Diagram.workshop_expires_at,
                ).filter(
                    Diagram.id == diagram_id,
                    ~Diagram.is_deleted,
                ),
            )
            row = result.first()
            if row is None:
                return None
            active_code, active_expires = row
            if not active_code:
                return None
            if active_expires and is_online_collab_expired(active_expires):
                return None
            return active_code
        except SQLAlchemyError as exc:
            logger.debug(
                "[OnlineCollabMgr] get_active_online_collab_code_for_diagram "
                "error diagram_id=%s: %s",
                diagram_id,
                exc,
            )
            return None


async def join_online_collab_impl(
    manager: Any,
    code: str,
    user_id: int,
) -> Optional[Dict[str, Any]]:
    """Join collaboration by shared code."""
    async with AsyncSessionLocal() as db:
        try:
            code = code.strip().upper()

            redis = get_async_redis()
            diagram_id = None
            if redis:
                diagram_id_raw = await redis.get(code_to_diagram_key(code))
                if diagram_id_raw:
                    diagram_id = (
                        diagram_id_raw
                        if isinstance(diagram_id_raw, str)
                        else diagram_id_raw.decode("utf-8")
                    )

            if not diagram_id:
                result = await db.execute(
                    select(Diagram).filter(
                        Diagram.workshop_code == code,
                        ~Diagram.is_deleted,
                    ),
                )
                diagram = result.scalars().first()
                if diagram:
                    diagram_id = diagram.id
                    if redis:
                        await backfill_online_collab_expiry_if_needed(diagram, db)
                        ttl = manager._redis_ttl_seconds_for_diagram(diagram)
                        await restore_online_collab_redis_from_db_row(
                            redis,
                            code,
                            diagram_id,
                            diagram,
                            ttl,
                        )

            if not diagram_id:
                logger.warning("[OnlineCollabMgr] Invalid workshop code: %s", code)
                return None

            result = await db.execute(
                select(Diagram).filter(
                    Diagram.id == diagram_id,
                    ~Diagram.is_deleted,
                ),
            )
            diagram = result.scalars().first()
            if not diagram:
                return None

            return await manager._finalize_join_after_load(
                db,
                redis,
                diagram,
                diagram_id,
                code,
                user_id,
            )

        except (SQLAlchemyError, OSError, RedisError) as exc:
            logger.error(
                "[OnlineCollabMgr] Error joining workshop: %s",
                exc,
                exc_info=True,
            )
            return None


async def join_online_collab_by_diagram_impl(
    manager: Any,
    diagram_id: str,
    user_id: int,
) -> Optional[Dict[str, Any]]:
    """Join organization-scoped session by diagram id."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Diagram).filter(
                Diagram.id == diagram_id,
                ~Diagram.is_deleted,
            ),
        )
        diagram = result.scalars().first()
        if not diagram or not diagram.workshop_code:
            return None
        if (
            diagram_online_collab_visibility(diagram)
            != ONLINE_COLLAB_VISIBILITY_ORGANIZATION
        ):
            return None
        if not await user_may_join_diagram_online_collab(db, diagram, user_id):
            logger.warning(
                "[OnlineCollabMgr] Org join denied user=%s diagram=%s",
                user_id,
                diagram_id,
            )
            return None
        org_code = diagram.workshop_code
    return await manager.join_online_collab(org_code, user_id)
