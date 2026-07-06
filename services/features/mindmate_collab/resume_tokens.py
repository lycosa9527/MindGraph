"""
MindMate collab join resume tokens (Redis-backed).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import secrets
from typing import Any, Dict, Optional

from services.features.mindmate_collab.config import MINDMATE_COLLAB_JOIN_RESUME_TTL_SEC
from services.features.mindmate_collab.redis_keys import join_resume_key, normalize_collab_code
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS


_MAX_RESUME_QUERY_LEN = 96


def _normalize_resume_token(token: str) -> str:
    trimmed = token.strip()
    if not trimmed or len(trimmed) > _MAX_RESUME_QUERY_LEN:
        return ""
    return trimmed


def _new_token() -> str:
    return secrets.token_hex(16)


async def mint_join_resume_token_async(
    user_id: int,
    code: str,
    session_id: str,
) -> str:
    """Store one-time join claims and return the resume token."""
    redis = get_async_redis()
    token = _new_token()
    if not redis:
        return ""
    payload = json.dumps(
        {"u": int(user_id), "c": normalize_collab_code(code), "s": session_id},
        separators=(",", ":"),
    )
    try:
        await redis.set(join_resume_key(token), payload, ex=MINDMATE_COLLAB_JOIN_RESUME_TTL_SEC)
    except REDIS_ERRORS:
        pass
    return token


async def peek_join_resume_claims_async(token: str) -> Optional[Dict[str, Any]]:
    """Read join resume claims without consuming the token."""
    normalized = _normalize_resume_token(token)
    if not normalized:
        return None
    redis = get_async_redis()
    if not redis:
        return None
    try:
        raw = await redis.get(join_resume_key(normalized))
    except REDIS_ERRORS:
        return None
    if not raw:
        return None
    text = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def join_resume_claims_match_user_room(
    user_id: int,
    code: str,
    claims: Dict[str, Any],
    session_id: str | None = None,
) -> bool:
    """Return True when resume claims match the joining user, room code, and session."""
    if int(claims.get("u") or 0) != int(user_id):
        return False
    if str(claims.get("c") or "").upper() != normalize_collab_code(code):
        return False
    if session_id is not None:
        claim_session = str(claims.get("s") or "").strip()
        if claim_session and claim_session != session_id:
            return False
    return True


async def try_consume_join_resume_token_async(token: str) -> Optional[Dict[str, Any]]:
    """Atomically read and delete join resume claims when present."""
    normalized = _normalize_resume_token(token)
    if not normalized:
        return None
    redis = get_async_redis()
    if not redis:
        return None
    key = join_resume_key(normalized)
    try:
        raw = await redis.getdel(key)
    except REDIS_ERRORS:
        claims = await peek_join_resume_claims_async(normalized)
        if claims:
            try:
                await redis.delete(key)
            except REDIS_ERRORS:
                pass
        return claims
    if not raw:
        return None
    text = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None
