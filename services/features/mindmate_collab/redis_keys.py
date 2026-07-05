"""
Redis keys for MindMate collab sessions.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Iterable, List

MINDMATE_COLLAB_REDIS_PREFIX = "mindmate_collab"
MINDMATE_COLLAB_FANOUT_ROOM_PREFIX = "mmc:"


def normalize_collab_code(code: str) -> str:
    """Uppercase and strip workshop-style code."""
    return (code or "").strip().upper()


def fanout_room_key(code: str) -> str:
    """Namespace fanout/registry keys away from canvas workshop codes."""
    return f"{MINDMATE_COLLAB_FANOUT_ROOM_PREFIX}{normalize_collab_code(code)}"


def session_meta_key(code: str) -> str:
    """Redis HASH key for room metadata."""
    return f"{MINDMATE_COLLAB_REDIS_PREFIX}:sessionmeta:{normalize_collab_code(code)}"


def participants_key(code: str) -> str:
    """Redis HASH key for active participant user ids."""
    return f"{MINDMATE_COLLAB_REDIS_PREFIX}:participants:{normalize_collab_code(code)}"


def code_to_session_key(code: str) -> str:
    """Redis STRING mapping room code to session UUID."""
    return f"{MINDMATE_COLLAB_REDIS_PREFIX}:code_to_session:{normalize_collab_code(code)}"


def registry_org_key(org_id: int) -> str:
    """Redis SET of live room codes for one organization."""
    return f"{MINDMATE_COLLAB_REDIS_PREFIX}:registry:org:{org_id}"


def registry_global_org_key() -> str:
    """Redis SET of live org-scoped rooms without organization_id."""
    return f"{MINDMATE_COLLAB_REDIS_PREFIX}:registry:org:global"


def registry_network_key() -> str:
    """Redis SET of live network-visible room codes."""
    return f"{MINDMATE_COLLAB_REDIS_PREFIX}:registry:network"


def idle_scores_key() -> str:
    """Redis ZSET of room codes scored by last activity unix time."""
    return f"{MINDMATE_COLLAB_REDIS_PREFIX}:idle_scores"


def closing_key(code: str) -> str:
    """Redis marker while a room is tearing down."""
    return f"{MINDMATE_COLLAB_REDIS_PREFIX}:closing:{normalize_collab_code(code)}"


def dify_stream_lock_key(code: str) -> str:
    """Redis lock key for single-writer Dify streaming."""
    return f"{MINDMATE_COLLAB_REDIS_PREFIX}:dify_stream:{normalize_collab_code(code)}"


def dify_stream_abort_key(code: str) -> str:
    """Redis marker requesting cooperative abort of an in-flight Dify stream."""
    return f"{MINDMATE_COLLAB_REDIS_PREFIX}:dify_abort:{normalize_collab_code(code)}"


def room_idle_warning_key(code: str) -> str:
    """Redis marker that an idle warning was broadcast."""
    return f"{MINDMATE_COLLAB_REDIS_PREFIX}:idle_warn:{normalize_collab_code(code)}"


def room_idle_kick_lock_key(code: str) -> str:
    """Redis lock key for idle teardown."""
    return f"{MINDMATE_COLLAB_REDIS_PREFIX}:idle_kick:{normalize_collab_code(code)}"


def start_lock_key(user_id: int) -> str:
    """Redis lock key while a user starts a room."""
    return f"{MINDMATE_COLLAB_REDIS_PREFIX}:start_lock:{user_id}"


def join_resume_key(token: str) -> str:
    """Redis STRING for one-time WebSocket join resume claims."""
    return f"{MINDMATE_COLLAB_REDIS_PREFIX}:ws:jresume:{token}"


def purge_session_redis_keys(_redis: Any, code: str, org_id: int | None, visibility: str) -> List[str]:
    """Delete Redis keys for one room (sync helper; caller runs in async context)."""
    norm = normalize_collab_code(code)
    keys: List[str] = [
        session_meta_key(norm),
        participants_key(norm),
        code_to_session_key(norm),
        closing_key(norm),
        dify_stream_lock_key(norm),
        dify_stream_abort_key(norm),
        room_idle_warning_key(norm),
        room_idle_kick_lock_key(norm),
    ]
    if org_id is not None:
        keys.append(registry_org_key(org_id))
    else:
        keys.append(registry_global_org_key())
    if visibility == "network":
        keys.append(registry_network_key())
    return keys


async def async_purge_session_redis_keys(
    redis: Any,
    code: str,
    org_id: int | None,
    visibility: str,
) -> None:
    """Remove session keys and registry membership."""
    norm = normalize_collab_code(code)
    pipe = redis.pipeline()
    for key in purge_session_redis_keys(redis, norm, org_id, visibility):
        if key.startswith(f"{MINDMATE_COLLAB_REDIS_PREFIX}:registry:"):
            continue
        pipe.delete(key)
    pipe.zrem(idle_scores_key(), norm)
    if org_id is not None:
        pipe.srem(registry_org_key(org_id), norm)
    else:
        pipe.srem(registry_global_org_key(), norm)
    if visibility == "network":
        pipe.srem(registry_network_key(), norm)
    await pipe.execute()


def registry_keys_for_visibility(org_id: int | None, visibility: str) -> Iterable[str]:
    """Yield registry SET keys that must track one room code."""
    if visibility == "network":
        yield registry_network_key()
        return
    if org_id is not None:
        yield registry_org_key(org_id)
    else:
        yield registry_global_org_key()
