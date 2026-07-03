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
        return token
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
    redis = get_async_redis()
    if not redis or not token:
        return None
    try:
        raw = await redis.get(join_resume_key(token.strip()))
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


def join_resume_claims_match_user_room(user_id: int, code: str, claims: Dict[str, Any]) -> bool:
    """Return True when resume claims match the joining user and room code."""
    return int(claims.get("u") or 0) == int(user_id) and str(claims.get("c") or "").upper() == normalize_collab_code(
        code
    )


async def try_consume_join_resume_token_async(token: str) -> Optional[Dict[str, Any]]:
    """Atomically read and delete join resume claims when present."""
    redis = get_async_redis()
    if not redis or not token:
        return None
    key = join_resume_key(token.strip())
    try:
        raw = await redis.getdel(key)
    except REDIS_ERRORS:
        claims = await peek_join_resume_claims_async(token)
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
