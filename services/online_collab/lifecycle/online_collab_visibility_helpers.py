"""
Workshop authorization and visibility helpers.

These are shared across ``workshop_service`` and ``workshop_status_ops``
to avoid circular imports.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.diagrams import Diagram
from services.online_collab.lifecycle.online_collab_expiry import is_online_collab_expired
from services.online_collab.redis.online_collab_redis_keys import purge_online_collab_redis_keys
from services.online_collab.lifecycle.online_collab_session_fields import (
    backfill_online_collab_expiry_if_needed,
    clear_online_collab_session_fields,
)

logger = logging.getLogger(__name__)

ONLINE_COLLAB_VISIBILITY_ORGANIZATION = "organization"
ONLINE_COLLAB_VISIBILITY_NETWORK = "network"
ONLINE_COLLAB_VISIBILITY_PRIVATE = "private"


def diagram_online_collab_visibility(diagram: Diagram) -> str:
    """Effective visibility: None/unknown defaults to private."""
    vis = getattr(diagram, "workshop_visibility", None)
    if vis == ONLINE_COLLAB_VISIBILITY_ORGANIZATION:
        return ONLINE_COLLAB_VISIBILITY_ORGANIZATION
    if vis == ONLINE_COLLAB_VISIBILITY_NETWORK:
        return ONLINE_COLLAB_VISIBILITY_NETWORK
    return ONLINE_COLLAB_VISIBILITY_PRIVATE


async def user_may_join_diagram_online_collab(
    db: AsyncSession,
    diagram: Diagram,
    joiner_id: int,
) -> bool:
    """
    Owner always joins. Admins may join. Same-organization as diagram owner may join.

    When the diagram owner has no organization (e.g. admin/superuser host),
    any authenticated org member may join an organization-visibility session.

    Uses a single IN query to fetch both joiner and owner user rows and
    projects only the columns we need (role, organization_id). This replaces
    two serial SELECT * round-trips with one column-projected SELECT.
    """
    if diagram.user_id == joiner_id:
        return True
    vis = diagram_online_collab_visibility(diagram)
    if vis == ONLINE_COLLAB_VISIBILITY_PRIVATE:
        return False
    owner_id = diagram.user_id
    ids = {joiner_id, owner_id}
    result = await db.execute(
        select(User.id, User.role, User.organization_id).where(User.id.in_(ids))
    )
    rows = result.all()
    joiner_row = None
    owner_row = None
    for row in rows:
        if row.id == joiner_id:
            joiner_row = row
        if row.id == owner_id:
            owner_row = row
    if joiner_row is None or owner_row is None:
        return False
    if joiner_row.role in ("admin", "superadmin", "manager"):
        return True
    org_joiner = joiner_row.organization_id
    org_owner = owner_row.organization_id
    if org_joiner is not None and org_owner is not None and org_joiner == org_owner:
        return True
    if org_owner is None and org_joiner is not None and vis == ONLINE_COLLAB_VISIBILITY_ORGANIZATION:
        return True
    return False


async def viewer_may_see_online_collab_code(
    db: AsyncSession,
    diagram: Diagram,
    viewer_id: int,
) -> bool:
    """
    Who may receive the join code via GET workshop/status.
    Owner always; organization sessions: same rules as join; network: owner only.
    """
    if diagram.user_id == viewer_id:
        return True
    vis = diagram_online_collab_visibility(diagram)
    if vis == ONLINE_COLLAB_VISIBILITY_NETWORK:
        return False
    return await user_may_join_diagram_online_collab(db, diagram, viewer_id)


async def clear_expired_online_collab_session(
    diagram: Diagram,
    db: AsyncSession,
    redis: Any,
) -> bool:
    """
    If the workshop session is expired, purge Redis keys and clear DB fields.

    Returns:
        True if the session was cleared, False if not expired or missing.
    """
    await backfill_online_collab_expiry_if_needed(diagram, db)
    if not diagram.workshop_code:
        return False
    if not diagram.workshop_expires_at:
        return False
    if not is_online_collab_expired(diagram.workshop_expires_at):
        return False
    code = diagram.workshop_code
    await purge_online_collab_redis_keys(redis, code)
    clear_online_collab_session_fields(diagram)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
    logger.info(
        "[WorkshopVisibilityHelpers] Cleared expired workshop for diagram %s",
        diagram.id,
    )
    return True
