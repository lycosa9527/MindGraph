"""Helpers for joining a workshop (Redis restore from DB)."""

import logging
from datetime import UTC, datetime
from typing import Any, Optional

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from config.database import AsyncSessionLocal
from models.domain.auth import User
from models.domain.diagrams import Diagram
from services.online_collab.lifecycle.online_collab_expiry import expires_at_to_unix
from services.online_collab.redis.online_collab_redis_keys import code_to_diagram_key, session_key

logger = logging.getLogger(__name__)


async def restore_online_collab_redis_from_db_row(
    redis: Any,
    code: str,
    diagram_id: str,
    diagram: Diagram,
    ttl: int,
    org_id: Optional[int] = None,
    visibility: Optional[str] = None,
    title: Optional[str] = None,
    owner_name: Optional[str] = None,
) -> None:
    """
    Re-seed Redis session + code_to_diagram after a DB fallback lookup.

    Also seeds the session manager meta hash, org registry, and idle_scores so
    restored sessions are visible to the idle monitor and org listing.
    """
    await redis.setex(
        code_to_diagram_key(code),
        ttl,
        diagram_id,
    )
    session_data = {
        "diagram_id": diagram_id,
        "owner_id": str(diagram.user_id),
        "created_at": (
            diagram.workshop_started_at.isoformat()
            if diagram.workshop_started_at
            else datetime.now(tz=UTC).isoformat()
        ),
    }
    await redis.setex(
        session_key(code),
        ttl,
        str(session_data),
    )

    resolved_visibility = visibility or getattr(diagram, "workshop_visibility", None) or "organization"
    resolved_org_id = org_id
    resolved_title = title or getattr(diagram, "title", "") or ""
    resolved_owner_name = owner_name or ""

    if resolved_org_id is None:
        owner_id = getattr(diagram, "user_id", None)
        if owner_id is not None:
            try:
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(User.organization_id, User.name).where(User.id == owner_id)
                    )
                    row = result.first()
                    if row:
                        resolved_org_id = row.organization_id
                        if not resolved_owner_name:
                            resolved_owner_name = row.name or ""
            except (SQLAlchemyError, OSError) as exc:
                logger.warning(
                    "[JoinHelpers] restore: could not fetch owner org for "
                    "code=%s owner_id=%s: %s",
                    code, owner_id, exc,
                )

    expires_at = getattr(diagram, "workshop_expires_at", None)
    expires_at_unix: int
    if expires_at:
        try:
            expires_at_unix = expires_at_to_unix(expires_at)
        except (AttributeError, TypeError, ValueError):
            expires_at_unix = 0
    else:
        expires_at_unix = 0

    try:
        from services.online_collab.core.online_collab_manager import (
            get_online_collab_manager,
        )
        await get_online_collab_manager().create_session(
            code=code,
            diagram_id=diagram_id,
            owner_id=int(diagram.user_id),
            org_id=resolved_org_id,
            visibility=resolved_visibility,
            expires_at_unix=expires_at_unix,
            ttl_sec=ttl,
            title=resolved_title,
            owner_name=resolved_owner_name,
        )
    except (RedisError, OSError, RuntimeError, TypeError, ValueError, AttributeError) as exc:
        logger.warning(
            "[JoinHelpers] restore: session manager seed failed code=%s: %s",
            code,
            exc,
        )
