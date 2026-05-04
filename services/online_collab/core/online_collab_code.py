"""Online collaboration session codes and start-path validation helpers."""

# Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
# All Rights Reserved
# Proprietary License

from __future__ import annotations

import logging
import os
import random
from datetime import datetime
from typing import Any, Optional

from models.domain.diagrams import Diagram

from services.online_collab.lifecycle.online_collab_expiry import (
    duration_allowed_for_visibility,
)
from services.online_collab.lifecycle.online_collab_visibility_helpers import (
    ONLINE_COLLAB_VISIBILITY_NETWORK,
    ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
)
from services.online_collab.redis.online_collab_redis_keys import code_to_diagram_key
from services.online_collab.redis.redis8_features import (
    bloom_add_online_collab_code,
    bloom_may_contain_online_collab_code,
)

logger = logging.getLogger(__name__)

ONLINE_COLLAB_CODE_PATTERN = "{}-{}"
ONLINE_COLLAB_CODE_LENGTH = 3
ONLINE_COLLAB_CODE_CHARSET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
ONLINE_COLLAB_CODE_RE = r"^[2-9A-HJ-KM-NP-Z]{3}-[2-9A-HJ-KM-NP-Z]{3}$"
ONLINE_COLLAB_SESSION_TTL = 86400


def _parse_online_collab_max_participants() -> int:
    raw = os.environ.get("WORKSHOP_MAX_PARTICIPANTS", "500")
    try:
        parsed = int(raw)
        return max(2, min(parsed, 10000))
    except ValueError:
        return 500


ONLINE_COLLAB_MAX_PARTICIPANTS = _parse_online_collab_max_participants()


def _online_collab_start_validation_error(
    diagram: Optional[Diagram],
    diagram_id: str,
    user_id: int,
    visibility: str,
    duration: str,
) -> Optional[str]:
    """Return an error message if start inputs are invalid, else None."""
    if not diagram:
        error_msg = f"Diagram {diagram_id} not found or not owned by user {user_id}"
        logger.warning("[OnlineCollabMgr] %s", error_msg)
        return error_msg
    if visibility not in (
        ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
        ONLINE_COLLAB_VISIBILITY_NETWORK,
    ):
        return "Invalid workshop visibility"
    if not duration_allowed_for_visibility(visibility, duration):
        return "Invalid duration for this visibility mode"
    return None


def _online_collab_start_session_redis_value(
    diagram_id: str,
    user_id: int,
    started_at: datetime,
) -> str:
    """Serialized session metadata for Redis ``workshop:session``."""
    return str(
        {
            "diagram_id": diagram_id,
            "owner_id": str(user_id),
            "created_at": started_at.isoformat(),
        }
    )


def generate_online_collab_code() -> str:
    """Generate XXX-XXX code from unambiguous charset."""
    part1 = "".join(
        random.choices(ONLINE_COLLAB_CODE_CHARSET, k=ONLINE_COLLAB_CODE_LENGTH),
    )
    part2 = "".join(
        random.choices(ONLINE_COLLAB_CODE_CHARSET, k=ONLINE_COLLAB_CODE_LENGTH),
    )
    return ONLINE_COLLAB_CODE_PATTERN.format(part1, part2)


async def _allocate_unique_online_collab_code(redis: Any) -> Optional[str]:
    """
    Pick a code with no existing code_to_diagram mapping, or None.

    Optionally uses COLLAB bloom backend for faster negative checks.
    """
    for _ in range(10):
        candidate = generate_online_collab_code()
        bloom_hit = await bloom_may_contain_online_collab_code(candidate)
        if bloom_hit:
            if await redis.get(code_to_diagram_key(candidate)):
                continue
        elif bloom_hit is False:
            await bloom_add_online_collab_code(candidate)
            return candidate
        if not await redis.get(code_to_diagram_key(candidate)):
            await bloom_add_online_collab_code(candidate)
            return candidate
    return None


__all__ = [
    "ONLINE_COLLAB_CODE_CHARSET",
    "ONLINE_COLLAB_CODE_LENGTH",
    "ONLINE_COLLAB_CODE_PATTERN",
    "ONLINE_COLLAB_CODE_RE",
    "ONLINE_COLLAB_MAX_PARTICIPANTS",
    "ONLINE_COLLAB_SESSION_TTL",
    "_allocate_unique_online_collab_code",
    "_online_collab_start_validation_error",
    "_online_collab_start_session_redis_value",
    "generate_online_collab_code",
]
