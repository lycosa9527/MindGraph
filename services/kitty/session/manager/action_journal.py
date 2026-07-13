"""Hot Session Manager action journal (Redis list per user+scope).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from redis.exceptions import RedisError

from services.kitty.infra.redis.kitty_redis_keys import (
    kitty_redis_ttl_seconds,
    kitty_session_journal_key,
)
from services.kitty.infra.scope.kitty_ws_scope import normalize_kitty_diagram_session_id
from services.kitty.session.manager.types import KittyJournalEvent
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_JOURNAL_MAX_LEN = 200
_TEXT_PREVIEW_MAX = 80


def text_preview_and_len(text: Optional[str]) -> tuple[Optional[str], Optional[int]]:
    """Return clipped preview + length for journal (full text stays in turns)."""
    if text is None:
        return None, None
    cleaned = " ".join(str(text).split()).strip()
    if not cleaned:
        return None, 0
    length = len(cleaned)
    if length <= _TEXT_PREVIEW_MAX:
        return cleaned, length
    return f"{cleaned[: _TEXT_PREVIEW_MAX - 1]}…", length


async def append_session_journal(event: KittyJournalEvent) -> None:
    """Append one journal event; best-effort when Redis is unavailable."""
    scope = normalize_kitty_diagram_session_id(event.diagram_scope)
    if scope is None:
        return
    try:
        uid = int(event.user_id)
    except (TypeError, ValueError):
        return
    if uid <= 0:
        return
    redis = get_async_redis()
    if redis is None:
        return
    key = kitty_session_journal_key(uid, scope)
    payload = event.to_dict()
    payload["diagram_scope"] = scope
    if event.ts <= 0:
        payload["ts"] = int(time.time())
    try:
        raw = json.dumps(payload, ensure_ascii=False)
        await redis.lpush(key, raw)
        await redis.ltrim(key, 0, _JOURNAL_MAX_LEN - 1)
        await redis.expire(key, kitty_redis_ttl_seconds())
    except (RedisError, TypeError, ValueError, AttributeError, RuntimeError) as exc:
        logger.debug(
            "[KittySessionJournal] append failed user=%s scope=%s: %s",
            uid,
            scope[:12],
            exc,
        )


async def append_journal_simple(
    *,
    kind: str,
    user_id: int,
    diagram_scope: str,
    lane: Optional[str] = None,
    voice_session_id: Optional[str] = None,
    request_id: Optional[str] = None,
    utterance_id: Optional[str] = None,
    ingress_source: Optional[str] = None,
    text: Optional[str] = None,
    action: Optional[str] = None,
    mutation_id: Optional[str] = None,
    outcome: Optional[str] = None,
    library_id: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    """Convenience wrapper for common journal kinds."""
    preview, text_len = text_preview_and_len(text)
    await append_session_journal(
        KittyJournalEvent(
            kind=kind,
            user_id=user_id,
            diagram_scope=diagram_scope,
            ts=int(time.time()),
            lane=lane,
            voice_session_id=voice_session_id,
            request_id=request_id,
            utterance_id=utterance_id,
            ingress_source=ingress_source,
            text_preview=preview,
            text_len=text_len,
            action=action,
            mutation_id=mutation_id,
            outcome=outcome,
            library_id=library_id,
            detail=dict(detail or {}),
        )
    )


async def read_session_journal(
    user_id: int,
    diagram_scope: str,
    *,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Return newest journal events (up to ``limit``)."""
    scope = normalize_kitty_diagram_session_id(diagram_scope)
    if scope is None:
        return []
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return []
    if uid <= 0:
        return []
    redis = get_async_redis()
    if redis is None:
        return []
    key = kitty_session_journal_key(uid, scope)
    cut = max(1, min(int(limit), _JOURNAL_MAX_LEN))
    try:
        rows = await redis.lrange(key, 0, cut - 1)
    except RedisError as exc:
        logger.debug(
            "[KittySessionJournal] read failed user=%s scope=%s: %s",
            uid,
            scope[:12],
            exc,
        )
        return []
    out: List[Dict[str, Any]] = []
    for raw in rows or []:
        try:
            text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            data = json.loads(text)
            if isinstance(data, dict):
                out.append(data)
        except (TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
            continue
    return out
