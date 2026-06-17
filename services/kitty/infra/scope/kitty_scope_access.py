"""Kitty WebSocket scope access — reject library diagram ids owned by other users.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy import select

from models.domain.diagrams import Diagram
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_LIBRARY_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def scope_looks_like_library_uuid(scope: str) -> bool:
    """True when the WS path segment matches a saved diagram library id shape."""
    return bool(_LIBRARY_UUID.match(scope))


async def user_may_access_kitty_scope(user_id: int, scope: str) -> bool:
    """
    Return whether ``user_id`` may open ``/ws/kitty/{scope}``.

    Ephemeral client-generated scopes are allowed when no library row exists.
    Library UUIDs must belong to the connecting user.
    """
    if not scope_looks_like_library_uuid(scope):
        return True

    cache = get_diagram_cache()
    owned = await cache.get_diagram(user_id, scope)
    if owned is not None:
        return True

    owner_id = await _library_diagram_owner_id(scope)
    if owner_id is None:
        return True

    if int(owner_id) == int(user_id):
        return True

    logger.warning(
        "Kitty WS scope denied: user_id=%s scope=%s owned_by=%s",
        user_id,
        scope[:16],
        owner_id,
    )
    return False


async def _library_diagram_owner_id(scope: str) -> Optional[int]:
    """Library diagram owner id."""
    try:
        async with system_rls_session() as db:
            result = await db.execute(
                select(Diagram.user_id)
                .where(
                    Diagram.id == scope,
                    Diagram.is_deleted.is_(False),
                )
                .limit(1)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return int(row)
    except (RuntimeError, ValueError, TypeError) as exc:
        logger.debug("Kitty scope owner lookup failed scope=%s: %s", scope[:16], exc)
        return None
