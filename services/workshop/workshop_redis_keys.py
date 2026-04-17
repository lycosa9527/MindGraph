"""
Redis key patterns and purge helper for workshop sessions.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any

WORKSHOP_SESSION_KEY = "workshop:session:{code}"
WORKSHOP_DIAGRAM_KEY = "workshop:diagram:{code}"
WORKSHOP_PARTICIPANTS_KEY = "workshop:participants:{code}"
WORKSHOP_CODE_TO_DIAGRAM_KEY = "workshop:code_to_diagram:{code}"
WORKSHOP_MUTATION_IDLE_KEY = "workshop:mutation_idle:{code}:{user_id}"
WORKSHOP_LIVE_SPEC_KEY = "workshop:live_spec:{code}"
WORKSHOP_LIVE_LAST_DB_FLUSH_KEY = "workshop:live_last_db_flush:{code}"


def session_key(code: str) -> str:
    """Redis key for workshop session metadata."""
    return WORKSHOP_SESSION_KEY.format(code=code)


def diagram_key(code: str) -> str:
    """Redis key for diagram payload (legacy/auxiliary)."""
    return WORKSHOP_DIAGRAM_KEY.format(code=code)


def participants_key(code: str) -> str:
    """Redis key for the participant set of a workshop."""
    return WORKSHOP_PARTICIPANTS_KEY.format(code=code)


def code_to_diagram_key(code: str) -> str:
    """Redis key mapping workshop code to diagram id."""
    return WORKSHOP_CODE_TO_DIAGRAM_KEY.format(code=code)


def mutation_idle_key(code: str, user_id: int) -> str:
    """Redis key for per-user mutation-idle TTL."""
    return WORKSHOP_MUTATION_IDLE_KEY.format(code=code, user_id=user_id)


def live_spec_key(code: str) -> str:
    """Redis JSON blob: merged diagram spec for the workshop (authoritative live state)."""
    return WORKSHOP_LIVE_SPEC_KEY.format(code=code)


def live_last_db_flush_key(code: str) -> str:
    """Unix timestamp (seconds) of last Diagram.spec flush for this workshop."""
    return WORKSHOP_LIVE_LAST_DB_FLUSH_KEY.format(code=code)


async def purge_workshop_redis_keys(redis: Any, code: str) -> None:
    """Remove Redis keys for a workshop code (best-effort)."""
    if not redis:
        return
    await redis.delete(session_key(code))
    await redis.delete(diagram_key(code))
    await redis.delete(participants_key(code))
    await redis.delete(code_to_diagram_key(code))
    await redis.delete(live_spec_key(code))
    await redis.delete(live_last_db_flush_key(code))
    try:
        async for key in redis.scan_iter(
            match=f"workshop:mutation_idle:{code}:*",
            count=50,
        ):
            await redis.delete(key)
    except (TypeError, AttributeError, RuntimeError):
        pass
