"""
Redis key patterns and purge helper for workshop sessions.

Cluster hash tagging
--------------------
When ``COLLAB_REDIS_HASH_TAGS=1`` is set, per-code keys are routed to the
same cluster slot by wrapping the dynamic segment in Redis Cluster hash tag
braces 鈥?e.g. ``workshop:live_spec:{ABC123}`` and
``workshop:participants:{ABC123}`` both hash to the same slot, which allows
multi-key commands (MULTI/EXEC, WATCH, EVAL, pipelines with MULTI) to work
under clustering. The flag must be set identically across all workers in the
deployment; a rolling flip between tagged and untagged layouts will leave
orphan keys until the session TTL expires.

Copyright 2024-2025 鍖椾含鎬濇簮鏅烘暀绉戞妧鏈夐檺鍏徃 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
from typing import Any

from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


def _use_cluster_hash_tags() -> bool:
    return os.getenv("COLLAB_REDIS_HASH_TAGS", "1") not in ("0", "false", "False", "")


def collab_hash_tags_enabled() -> bool:
    """
    True when ``COLLAB_REDIS_HASH_TAGS=1`` so per-code keys share a cluster slot.

    Callers that issue ``MULTI/EXEC`` across ``live_spec``, ``snapshot_seq``,
    and ``live_changed_keys`` must use ``transaction=True`` only when this is
    true (otherwise use non-transactional pipelines on Redis Cluster).
    """
    return _use_cluster_hash_tags()


def _tag(value: Any) -> str:
    """Return ``{value}`` when cluster hash tags are enabled, else ``value``."""
    s = str(value)
    if _use_cluster_hash_tags():
        return "{" + s + "}"
    return s

# ---------------------------------------------------------------------------
# Key templates 鈥?existing
# ---------------------------------------------------------------------------
ONLINE_COLLAB_SESSION_KEY = "workshop:session:{code}"
ONLINE_COLLAB_DIAGRAM_KEY = "workshop:diagram:{code}"
ONLINE_COLLAB_PARTICIPANTS_KEY = "workshop:participants:{code}"
ONLINE_COLLAB_CODE_TO_DIAGRAM_KEY = "workshop:code_to_diagram:{code}"
ONLINE_COLLAB_MUTATION_IDLE_KEY = "workshop:mutation_idle:{code}:{user_id}"
ONLINE_COLLAB_LIVE_SPEC_KEY = "workshop:live_spec:{code}"
ONLINE_COLLAB_LIVE_LAST_DB_FLUSH_KEY = "workshop:live_last_db_flush:{code}"
ONLINE_COLLAB_LIVE_FLUSH_PENDING_KEY = "workshop:live_flush_pending:{code}"

ONLINE_COLLAB_LIVE_CHANGED_KEYS_KEY = "workshop:live_changed_keys:{code}"
ONLINE_COLLAB_ROOM_LAST_COLLAB_TS_KEY = "workshop:room_last_collab_ts:{code}"
ONLINE_COLLAB_ROOM_IDLE_WARN_SENT_KEY = "workshop:room_idle_warn_sent:{code}"
ONLINE_COLLAB_ROOM_IDLE_KICK_LOCK_KEY = "workshop:room_idle_kick_lock:{code}"
ONLINE_COLLAB_DESTROY_LOCK_KEY = "workshop:destroy_lock:{code}"
ONLINE_COLLAB_START_LOCK_KEY = "workshop:start_lock:{diagram_id}"
ONLINE_COLLAB_SESSION_CLOSING_KEY = "workshop:closing:{code}"
ONLINE_COLLAB_LIVE_WRITE_LOCK_KEY = "workshop:write_lock:{code}"

# ---------------------------------------------------------------------------
# Key templates 鈥?session manager
# ---------------------------------------------------------------------------
ONLINE_COLLAB_SNAPSHOT_KEY = "workshop:snapshot:{code}"
ONLINE_COLLAB_SNAPSHOT_SEQ_KEY = "workshop:snapshot_seq:{code}"
ONLINE_COLLAB_SNAPSHOT_LEADER_KEY = "workshop:snapshot_leader:{code}"
ONLINE_COLLAB_TOMBSTONES_KEY = "workshop:tombstones:{code}"

# ---------------------------------------------------------------------------
# Key templates — session manager
# ---------------------------------------------------------------------------
ONLINE_COLLAB_SESSION_META_KEY = "workshop:sessionmeta:{code}"
ONLINE_COLLAB_REGISTRY_ORG_KEY = "workshop:registry:org:{org_id}"
ONLINE_COLLAB_REGISTRY_NETWORK_KEY = "workshop:registry:network"
ONLINE_COLLAB_REGISTRY_GLOBAL_ORG_KEY = "workshop:registry:org:global"
ONLINE_COLLAB_IDLE_SCORES_KEY = "workshop:idle_scores"


# ---------------------------------------------------------------------------
# Helpers 鈥?existing
# ---------------------------------------------------------------------------

def session_key(code: str) -> str:
    """Redis key for workshop session metadata (legacy string key)."""
    return ONLINE_COLLAB_SESSION_KEY.format(code=_tag(code))


def diagram_key(code: str) -> str:
    """Redis key for diagram payload (legacy/auxiliary)."""
    return ONLINE_COLLAB_DIAGRAM_KEY.format(code=_tag(code))


def participants_key(code: str) -> str:
    """Redis key for the participant set of a workshop."""
    return ONLINE_COLLAB_PARTICIPANTS_KEY.format(code=_tag(code))


def code_to_diagram_key(code: str) -> str:
    """Redis key mapping workshop code to diagram id."""
    return ONLINE_COLLAB_CODE_TO_DIAGRAM_KEY.format(code=_tag(code))


def mutation_idle_key(code: str, user_id: int) -> str:
    """Redis key for per-user mutation-idle TTL."""
    return ONLINE_COLLAB_MUTATION_IDLE_KEY.format(code=_tag(code), user_id=user_id)


def live_spec_key(code: str) -> str:
    """Redis JSON blob: merged diagram spec for the workshop (authoritative live state)."""
    return ONLINE_COLLAB_LIVE_SPEC_KEY.format(code=_tag(code))


def live_changed_keys_key(code: str) -> str:
    """Redis SET tracking which top-level JSONB keys changed since last flush."""
    return ONLINE_COLLAB_LIVE_CHANGED_KEYS_KEY.format(code=_tag(code))


def live_last_db_flush_key(code: str) -> str:
    """Unix timestamp (seconds) of last Diagram.spec flush for this workshop."""
    return ONLINE_COLLAB_LIVE_LAST_DB_FLUSH_KEY.format(code=_tag(code))


def live_flush_pending_key(code: str) -> str:
    """NX guard so only one worker schedules the debounced DB flush per workshop."""
    return ONLINE_COLLAB_LIVE_FLUSH_PENDING_KEY.format(code=_tag(code))


def room_last_collab_activity_key(code: str) -> str:
    """Unix timestamp (seconds) of last merged diagram collaborative update."""
    return ONLINE_COLLAB_ROOM_LAST_COLLAB_TS_KEY.format(code=_tag(code))


def room_idle_warning_sent_key(code: str) -> str:
    """NX guard + dedup marker for broadcasting the idle-warning window."""
    return ONLINE_COLLAB_ROOM_IDLE_WARN_SENT_KEY.format(code=_tag(code))


def snapshot_key(code: str) -> str:
    """Redis STRING: latest viewer snapshot JSON (spec + seq + ts), TTL 30 s."""
    return ONLINE_COLLAB_SNAPSHOT_KEY.format(code=_tag(code))


def snapshot_seq_key(code: str) -> str:
    """Redis counter: monotonic sequence number incremented on each edit."""
    return ONLINE_COLLAB_SNAPSHOT_SEQ_KEY.format(code=_tag(code))


def snapshot_leader_key(code: str) -> str:
    """NX leader-election key for the snapshot refresh task (tagged for cluster slot alignment)."""
    return ONLINE_COLLAB_SNAPSHOT_LEADER_KEY.format(code=_tag(code))


def tombstones_key(code: str) -> str:
    """SET of recently deleted node ids (short TTL) to reject stale cross-frame patches."""
    return ONLINE_COLLAB_TOMBSTONES_KEY.format(code=_tag(code))


def client_op_dedupe_key(code: str, user_id: int, client_op_id: str) -> str:
    """SETNX guard: at-most-once application of a queued collab update per (room, user, op)."""
    safe_id = str(client_op_id).strip()[:128]
    return f"workshop:client_op_dedupe:{_tag(code)}:{user_id}:{safe_id}"


def resync_rate_limit_key(code: str, user_id: int) -> str:
    """Per-(room, user) rolling window counter for ``resync`` frames."""
    return f"workshop:resync_rl:{_tag(code)}:{user_id}"


def room_idle_kick_lock_key(code: str) -> str:
    """NX guard so only one worker ends the workshop on idle expiry."""
    return ONLINE_COLLAB_ROOM_IDLE_KICK_LOCK_KEY.format(code=_tag(code))


def destroy_lock_key(code: str) -> str:
    """NX guard so only one worker destroys a workshop session."""
    return ONLINE_COLLAB_DESTROY_LOCK_KEY.format(code=_tag(code))


def start_lock_key(diagram_id: str) -> str:
    """NX lock that serialises concurrent start_online_collab calls for the same diagram."""
    return ONLINE_COLLAB_START_LOCK_KEY.format(diagram_id=_tag(diagram_id))


def session_closing_key(code: str) -> str:
    """NX-style marker while a workshop flush/stop window is active (suppresses live merges)."""
    return ONLINE_COLLAB_SESSION_CLOSING_KEY.format(code=_tag(code))


def live_write_lock_key(code: str) -> str:
    """Short-lived NX lock that serialises concurrent JSON writes per room across workers."""
    return ONLINE_COLLAB_LIVE_WRITE_LOCK_KEY.format(code=_tag(code))


# ---------------------------------------------------------------------------
# Helpers 鈥?session manager
# ---------------------------------------------------------------------------

def session_meta_key(code: str) -> str:
    """Redis HASH: full session metadata managed by OnlineCollabManager."""
    return ONLINE_COLLAB_SESSION_META_KEY.format(code=_tag(code))


def registry_org_key(org_id: int) -> str:
    """Redis SET of active workshop codes visible within a single organization."""
    return ONLINE_COLLAB_REGISTRY_ORG_KEY.format(org_id=_tag(org_id))


def registry_network_key() -> str:
    """Redis SET of active network-scope workshop codes (cross-org)."""
    return ONLINE_COLLAB_REGISTRY_NETWORK_KEY


def registry_global_org_key() -> str:
    """
    Redis SET for organization-visibility sessions hosted by org-less users (admins).

    When a host has no ``organization_id`` but starts a session with
    ``visibility="organization"``, the code is registered here so it appears in
    every org's listing without requiring the host to belong to a specific org.
    """
    return ONLINE_COLLAB_REGISTRY_GLOBAL_ORG_KEY


def idle_scores_key() -> str:
    """Redis ZSET: code 鈫?last_activity unix timestamp for idle monitoring."""
    return ONLINE_COLLAB_IDLE_SCORES_KEY


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _decode_bytes(val: Any) -> str:
    """Safely decode a bytes / memoryview / str value to str."""
    if isinstance(val, (bytes, bytearray)):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, memoryview):
        return bytes(val).decode("utf-8", errors="replace")
    return str(val) if val is not None else ""


# ---------------------------------------------------------------------------
# Purge helper
# ---------------------------------------------------------------------------

async def purge_online_collab_redis_keys(redis: Any, code: str) -> None:
    """
    Remove all Redis keys for a workshop code.

    Steps:
      1. Read the session-meta hash (1 round-trip) to resolve org_id / visibility
         so the correct registry SET entry can be removed.
      2. Pipeline-delete same-slot per-code keys.
      3. Separately clean global indexes (ZSET/registry SETs). Those keys do not
         share the room hash slot on Redis Cluster, so they must not be included
         in the same MULTI/EXEC as tagged room keys.
      3. Scan-delete per-user mutation_idle keys (requires scan; not pipelinable).
    """
    if not redis:
        return

    meta: dict = {}
    try:
        meta = await redis.hgetall(session_meta_key(code)) or {}
    except (RedisError, OSError, RuntimeError, TypeError, AttributeError) as exc:
        logger.debug(
            "[OnlineCollabRedisKeys] purge: hgetall meta failed code=%s: %s", code, exc
        )

    org_id_str = _decode_bytes(meta.get(b"org_id") or meta.get("org_id"))
    visibility = _decode_bytes(meta.get(b"visibility") or meta.get("visibility"))

    per_code_keys = [
        session_key(code),
        session_meta_key(code),
        diagram_key(code),
        participants_key(code),
        code_to_diagram_key(code),
        live_spec_key(code),
        live_changed_keys_key(code),
        live_last_db_flush_key(code),
        live_flush_pending_key(code),
        room_last_collab_activity_key(code),
        room_idle_warning_sent_key(code),
        room_idle_kick_lock_key(code),
        destroy_lock_key(code),
        snapshot_key(code),
        snapshot_seq_key(code),
        snapshot_leader_key(code),
        tombstones_key(code),
        session_closing_key(code),
        live_write_lock_key(code),
        f"mg:ws:workshop:editors:{_tag(code)}",
        f"mg:ws:workshop:editors_h:{_tag(code)}",
    ]
    try:
        async with redis.pipeline(transaction=_use_cluster_hash_tags()) as pipe:
            pipe.delete(*per_code_keys)
            await pipe.execute()
    except (RedisError, OSError, RuntimeError, TypeError) as exc:
        logger.warning(
            "[OnlineCollabRedisKeys] purge pipeline error code=%s: %s — per-key fallback",
            code, exc,
        )
        await _purge_keys_per_key_fallback(redis, per_code_keys)

    await _purge_global_indexes(redis, code, org_id_str, visibility)

    try:
        batch: list = []
        batch_limit = 500
        async for key in redis.scan_iter(
            match=f"workshop:mutation_idle:{_tag(code)}:*",
            count=200,
        ):
            batch.append(key)
            if len(batch) >= batch_limit:
                await _pipelined_unlink(redis, batch)
                batch = []
        if batch:
            await _pipelined_unlink(redis, batch)
    except (RedisError, OSError, TypeError, AttributeError, RuntimeError) as exc:
        logger.warning(
            "[OnlineCollabRedisKeys] purge scan_iter mutation_idle failed "
            "code=%s: %s",
            code, exc,
        )


async def _purge_global_indexes(
    redis: Any,
    code: str,
    org_id_str: str,
    visibility: str,
) -> None:
    """Best-effort cleanup for indexes that are not in the room hash slot."""
    try:
        await redis.zrem(idle_scores_key(), code)
    except (RedisError, OSError, RuntimeError, TypeError) as exc:
        logger.debug("[OnlineCollabRedisKeys] idle_scores zrem failed: %s", exc)

    candidate_registry_keys = {registry_global_org_key(), registry_network_key()}
    if org_id_str:
        try:
            candidate_registry_keys.add(registry_org_key(int(org_id_str)))
        except ValueError:
            logger.debug(
                "[OnlineCollabRedisKeys] invalid org_id in meta code=%s org_id=%s",
                code,
                org_id_str,
            )
    elif visibility == "organization":
        candidate_registry_keys.add(registry_global_org_key())
    elif visibility == "network":
        candidate_registry_keys.add(registry_network_key())
    else:
        await _purge_unknown_org_registries(redis, code, candidate_registry_keys)

    for registry_key in candidate_registry_keys:
        try:
            await redis.srem(registry_key, code)
        except (RedisError, OSError, RuntimeError, TypeError) as exc:
            logger.debug(
                "[OnlineCollabRedisKeys] registry srem failed key=%s code=%s: %s",
                registry_key,
                code,
                exc,
            )


async def _purge_unknown_org_registries(
    redis: Any,
    code: str,
    candidate_registry_keys: set[str],
) -> None:
    """
    Recover from missing session_meta by scanning org registry keys.

    This path is intentionally best-effort and only used when the reverse mapping
    needed for a precise SREM is unavailable.
    """
    try:
        async for key in redis.scan_iter(match="workshop:registry:org:*", count=100):
            decoded = _decode_bytes(key)
            if decoded:
                candidate_registry_keys.add(decoded)
    except (RedisError, OSError, RuntimeError, TypeError, AttributeError) as exc:
        logger.debug(
            "[OnlineCollabRedisKeys] registry scan failed code=%s: %s",
            code,
            exc,
        )


async def _purge_keys_per_key_fallback(redis: Any, keys: list) -> None:
    """
    Delete each key individually using UNLINK.

    Used when the cluster returns MOVED for a multi-key pipeline command
    (i.e., when hash tags are off and keys span multiple slots).
    """
    for key in keys:
        try:
            await redis.unlink(key)
        except (RedisError, OSError, RuntimeError, TypeError, AttributeError) as exc:
            logger.debug(
                "[OnlineCollabRedisKeys] per-key UNLINK failed key=%s: %s", key, exc
            )
            try:
                await redis.delete(key)
            except (RedisError, OSError, RuntimeError, TypeError, AttributeError):
                pass


async def _pipelined_unlink(redis: Any, keys: list) -> None:
    """
    Issue ``UNLINK`` for a batch of keys in a single pipeline round-trip.

    UNLINK (vs DEL) removes the key from the keyspace immediately but frees
    the memory asynchronously in a background thread, which avoids blocking
    the main Redis thread when deleting large structures. Falls back to DEL
    on servers that don't support UNLINK.
    """
    if not redis or not keys:
        return
    try:
        async with redis.pipeline(transaction=False) as pipe:
            for k in keys:
                pipe.unlink(k)
            await pipe.execute()
    except (RedisError, OSError, RuntimeError, TypeError, AttributeError) as exc:
        logger.debug(
            "[OnlineCollabRedisKeys] UNLINK batch failed (falling back to DEL): %s",
            exc,
        )
        try:
            async with redis.pipeline(transaction=False) as pipe:
                for k in keys:
                    pipe.delete(k)
                await pipe.execute()
        except (RedisError, OSError, RuntimeError, TypeError, AttributeError) as del_exc:
            logger.debug(
                "[OnlineCollabRedisKeys] DEL batch fallback failed: %s", del_exc,
            )
