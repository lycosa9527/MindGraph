"""Persist 一句话生成 (one-sentence panel) chat turns in Redis for session restore and analytics.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from redis.exceptions import RedisError

from services.kitty.infra.redis.kitty_redis_keys import (
    kitty_one_sentence_meta_key,
    kitty_one_sentence_turns_key,
    kitty_redis_ttl_seconds,
    kitty_scope_owner_key,
)
from services.kitty.infra.scope.kitty_scope_access import user_may_access_kitty_scope
from services.kitty.session.one_sentence_session_pg import (
    ensure_one_sentence_session,
    migrate_one_sentence_scope_pg,
)
from services.kitty.session.one_sentence_turn_pg import (
    list_one_sentence_turns_pg,
    schedule_one_sentence_turn_pg,
)
from services.kitty.session.runtime_state import voice_sessions
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

MAX_ONE_SENTENCE_TURNS = 200
MAX_ONE_SENTENCE_CONTENT_CHARS = 8000
_VALID_ROLES = frozenset({"user", "kitty", "meta"})
_VALID_PHASES = frozenset({"create", "edit"})


def _trim_content(text: str) -> str:
    cleaned = str(text or "").strip()
    if len(cleaned) > MAX_ONE_SENTENCE_CONTENT_CHARS:
        return cleaned[:MAX_ONE_SENTENCE_CONTENT_CHARS]
    return cleaned


def _normalize_turn_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    role = str(payload.get("role") or "").strip()
    if role not in _VALID_ROLES:
        return None
    content = _trim_content(str(payload.get("content") or ""))
    if role != "meta" and not content:
        return None

    phase = str(payload.get("phase") or "edit").strip()
    if phase not in _VALID_PHASES:
        phase = "edit"

    turn: Dict[str, Any] = {
        "turn_id": str(payload.get("turn_id") or uuid.uuid4().hex),
        "ts": int(payload.get("ts") or time.time()),
        "role": role,
        "content": content,
        "phase": phase,
        "source": str(payload.get("source") or "unknown").strip() or "unknown",
    }

    for optional_key in (
        "action",
        "outcome",
        "diagram_type",
        "voice_session_id",
        "user_text",
    ):
        value = payload.get(optional_key)
        if value is not None and str(value).strip():
            turn[optional_key] = str(value).strip()

    return turn


async def _read_meta(scope: str) -> Optional[Dict[str, Any]]:
    redis = get_async_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(kitty_one_sentence_meta_key(scope))
        if not raw:
            return None
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except (RedisError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.debug("[OneSentenceTurns] meta read failed scope=%s: %s", scope[:16], exc)
        return None


async def _user_may_read_scope(scope: str, user_id: int) -> bool:
    meta = await _read_meta(scope)
    if meta is not None:
        owner = meta.get("user_id")
        if owner is not None and int(owner) == int(user_id):
            return True

    redis = get_async_redis()
    if redis is not None:
        try:
            raw_owner = await redis.get(kitty_scope_owner_key(scope))
            if raw_owner:
                owner_text = raw_owner.decode("utf-8") if isinstance(raw_owner, bytes) else raw_owner
                if str(owner_text).strip() == str(int(user_id)):
                    return True
        except (RedisError, TypeError, ValueError, UnicodeDecodeError):
            pass

    return await user_may_access_kitty_scope(user_id, scope)


async def append_one_sentence_turn(
    scope: str,
    user_id: int,
    payload: Dict[str, Any],
    *,
    organization_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Append one turn to the scoped one-sentence log. Returns normalized turn or None."""
    turn = _normalize_turn_payload(payload)
    if turn is None:
        return None

    session_id = await ensure_one_sentence_session(
        user_id=user_id,
        organization_id=organization_id,
        diagram_scope=scope,
        diagram_type=str(turn.get("diagram_type") or "") or None,
    )
    if session_id:
        turn["session_id"] = session_id

    redis = get_async_redis()
    if redis is None:
        return None

    ttl = kitty_redis_ttl_seconds()
    meta_key = kitty_one_sentence_meta_key(scope)
    turns_key = kitty_one_sentence_turns_key(scope)

    try:
        meta = await _read_meta(scope)
        if meta is not None:
            owner = int(meta.get("user_id", -1))
            if owner != int(user_id):
                return None
        else:
            if not await user_may_access_kitty_scope(user_id, scope):
                return None
            meta = {
                "user_id": int(user_id),
                "scope": scope,
                "created_at": int(time.time()),
            }

        if turn.get("diagram_type"):
            meta["diagram_type"] = turn["diagram_type"]
        if session_id:
            meta["session_id"] = session_id
        meta["updated_at"] = int(time.time())
        meta["turn_count"] = int(meta.get("turn_count", 0)) + 1

        encoded_turn = json.dumps(turn, ensure_ascii=False)
        async with redis.pipeline(transaction=False) as pipe:
            pipe.set(meta_key, json.dumps(meta, ensure_ascii=False), ex=ttl)
            pipe.rpush(turns_key, encoded_turn)
            pipe.ltrim(turns_key, -MAX_ONE_SENTENCE_TURNS, -1)
            pipe.expire(turns_key, ttl)
            await pipe.execute()
        schedule_one_sentence_turn_pg(
            user_id=user_id,
            organization_id=organization_id,
            scope=scope,
            turn=turn,
        )
        return turn
    except (RedisError, TypeError, ValueError) as exc:
        logger.warning("[OneSentenceTurns] append failed scope=%s: %s", scope[:16], exc)
        return None


async def append_one_sentence_turns_batch(
    scope: str,
    user_id: int,
    turns: List[Dict[str, Any]],
    *,
    organization_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Append multiple turns (create-phase UI replay). Returns successfully stored turns."""
    stored: List[Dict[str, Any]] = []
    for item in turns:
        if not isinstance(item, dict):
            continue
        row = await append_one_sentence_turn(
            scope,
            user_id,
            item,
            organization_id=organization_id,
        )
        if row is not None:
            stored.append(row)
    return stored


async def list_one_sentence_turns(
    scope: str,
    user_id: int,
    *,
    limit: int = 100,
    include_meta: bool = False,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return turns oldest-first for UI restore and analytics export."""
    cap = max(1, min(limit, MAX_ONE_SENTENCE_TURNS))

    pg_turns = await list_one_sentence_turns_pg(
        scope=scope,
        user_id=user_id,
        limit=cap,
        session_id=session_id,
    )
    if pg_turns:
        payload: Dict[str, Any] = {"ok": True, "turns": pg_turns, "storage": "postgres"}
        if include_meta:
            meta = await _read_meta(scope)
            if session_id and meta is not None:
                meta["session_id"] = session_id
            payload["meta"] = meta
            if session_id:
                payload["session_id"] = session_id
        return payload

    if not await _user_may_read_scope(scope, user_id):
        return {"ok": False, "reason": "access_denied", "turns": []}

    redis = get_async_redis()
    if redis is None:
        return {"ok": False, "reason": "redis_unavailable", "turns": []}

    turns_key = kitty_one_sentence_turns_key(scope)
    try:
        raw_rows = await redis.lrange(turns_key, -cap, -1)
        turns: List[Dict[str, Any]] = []
        for raw in raw_rows or []:
            text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            try:
                parsed = json.loads(text)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if isinstance(parsed, dict):
                turns.append(parsed)

        redis_payload: Dict[str, Any] = {"ok": True, "turns": turns, "storage": "redis"}
        if include_meta:
            redis_payload["meta"] = await _read_meta(scope)
        return redis_payload
    except (RedisError, TypeError, ValueError, UnicodeDecodeError) as exc:
        logger.warning("[OneSentenceTurns] list failed scope=%s: %s", scope[:16], exc)
        return {"ok": False, "reason": "read_failed", "turns": []}


def _is_one_sentence_panel(session: Dict[str, Any]) -> bool:
    panel = str(session.get("active_panel") or "").strip()
    return panel == "one_sentence"


async def persist_one_sentence_turn_from_voice_session(
    voice_session_id: str,
    *,
    role: str,
    content: str,
    source: str,
    phase: str = "edit",
    action: Optional[str] = None,
    outcome: Optional[str] = None,
    user_text: Optional[str] = None,
    organization_id: Optional[int] = None,
) -> None:
    """Persist a turn when the Kitty WS session is the one-sentence panel."""
    session = voice_sessions.get(voice_session_id)
    if session is None or not _is_one_sentence_panel(session):
        return

    scope = str(session.get("diagram_session_id") or "").strip()
    if not scope:
        return

    user_raw = session.get("user_id")
    if user_raw is None:
        return
    try:
        user_id = int(user_raw)
    except (TypeError, ValueError):
        return

    payload: Dict[str, Any] = {
        "role": role,
        "content": content,
        "phase": phase,
        "source": source,
        "diagram_type": session.get("diagram_type"),
        "voice_session_id": voice_session_id,
    }

    if action and str(action).strip():
        payload["action"] = str(action).strip()
    if outcome and str(outcome).strip():
        payload["outcome"] = str(outcome).strip()
    if user_text and str(user_text).strip():
        payload["user_text"] = _trim_content(str(user_text))

    await append_one_sentence_turn(
        scope,
        user_id,
        payload,
        organization_id=organization_id,
    )


async def migrate_one_sentence_scope(
    *,
    user_id: int,
    from_scope: str,
    to_scope: str,
) -> Dict[str, Any]:
    """Move Redis + PostgreSQL one-sentence history from ephemeral to library scope."""
    source_scope = str(from_scope or "").strip()
    target_scope = str(to_scope or "").strip()
    if not source_scope or not target_scope or source_scope == target_scope:
        return {"ok": True, "migrated": False, "reason": "same_scope"}
    if user_id <= 0:
        return {"ok": False, "reason": "invalid_user"}

    if not await user_may_access_kitty_scope(user_id, source_scope):
        return {"ok": False, "reason": "access_denied"}
    if not await user_may_access_kitty_scope(user_id, target_scope):
        return {"ok": False, "reason": "access_denied"}

    pg_ok = await migrate_one_sentence_scope_pg(
        user_id=user_id,
        from_scope=source_scope,
        to_scope=target_scope,
    )
    if not pg_ok:
        return {"ok": False, "reason": "postgres_failed"}

    redis = get_async_redis()
    if redis is None:
        return {"ok": True, "migrated": True, "storage": "postgres_only"}

    ttl = kitty_redis_ttl_seconds()
    source_meta_key = kitty_one_sentence_meta_key(source_scope)
    source_turns_key = kitty_one_sentence_turns_key(source_scope)
    target_meta_key = kitty_one_sentence_meta_key(target_scope)
    target_turns_key = kitty_one_sentence_turns_key(target_scope)

    try:
        source_meta = await _read_meta(source_scope)
        source_rows = await redis.lrange(source_turns_key, 0, -1)
        if not source_rows:
            await redis.delete(source_meta_key, source_turns_key)
            return {"ok": True, "migrated": True, "storage": "postgres"}

        target_meta = await _read_meta(target_scope)
        merged_meta: Dict[str, Any] = dict(target_meta or source_meta or {})
        merged_meta["user_id"] = int(user_id)
        merged_meta["scope"] = target_scope
        merged_meta["updated_at"] = int(time.time())
        if source_meta:
            merged_meta["turn_count"] = int(merged_meta.get("turn_count", 0)) + int(source_meta.get("turn_count", 0))

        async with redis.pipeline(transaction=False) as pipe:
            for raw in source_rows:
                pipe.rpush(target_turns_key, raw)
            pipe.ltrim(target_turns_key, -MAX_ONE_SENTENCE_TURNS, -1)
            pipe.expire(target_turns_key, ttl)
            pipe.set(target_meta_key, json.dumps(merged_meta, ensure_ascii=False), ex=ttl)
            pipe.delete(source_meta_key, source_turns_key)
            await pipe.execute()
        return {"ok": True, "migrated": True, "storage": "redis_and_postgres"}
    except (RedisError, TypeError, ValueError) as exc:
        logger.warning(
            "[OneSentenceTurns] redis migrate failed %s->%s: %s",
            source_scope[:16],
            target_scope[:16],
            exc,
        )
        return {"ok": True, "migrated": True, "storage": "postgres_only", "redis_warning": str(exc)}
