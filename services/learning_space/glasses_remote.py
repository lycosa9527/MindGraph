"""Queue canvas nudges from a bound pair of glasses to that user's open editor.

The glasses remember the bind QR they photographed. That token is the capability.
The signed-in editor drains the queue while the diagram is open.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select

from models.domain.learning_space import GlassesWearerBind
from services.learning_space.glasses_contract import (
    REMOTE_DISPLAY,
    normalize_remote_action,
    sheet_id_from_payload,
)
from services.learning_space.glasses_events import publish_glasses_event
from services.redis.redis_client import get_redis
from services.utils.error_types import REDIS_ERRORS
from utils.db.session_open import system_rls_session

KEY_PREFIX = "mg:glasses:remote:"
TTL_SECONDS = 20
MAX_QUEUED = 32


def remote_key(user_id: int) -> str:
    """Redis list of pending canvas actions for one account."""
    return f"{KEY_PREFIX}{int(user_id)}"


def push_remote_action(redis: Any, user_id: int, action: str) -> bool:
    """Append one action. False when the action is unknown or Redis refuses."""
    act = normalize_remote_action(action)
    if redis is None or not act:
        return False
    key = remote_key(user_id)
    try:
        redis.rpush(key, act)
        redis.ltrim(key, -MAX_QUEUED, -1)
        redis.expire(key, TTL_SECONDS)
    except REDIS_ERRORS:
        return False
    return True


def take_remote_actions(redis: Any, user_id: int) -> list[str]:
    """Read and clear the queue, oldest first."""
    if redis is None:
        return []
    key = remote_key(user_id)
    try:
        raw = redis.lrange(key, 0, -1) or []
        redis.delete(key)
    except REDIS_ERRORS:
        return []
    actions: list[str] = []
    for item in raw:
        text = item.decode("utf-8") if isinstance(item, bytes) else str(item)
        act = normalize_remote_action(text)
        if act:
            actions.append(act)
    return actions


async def _bound_owner_id(token: str) -> int | None:
    token_id = sheet_id_from_payload(token) or (token or "").strip()
    if len(token_id) != 36:
        return None
    async with system_rls_session() as db:
        result = await db.execute(select(GlassesWearerBind).where(GlassesWearerBind.id == token_id))
        row = result.scalar_one_or_none()
    if row is None or row.bound_at is None:
        return None
    return int(row.owner_user_id)


async def enqueue_glasses_remote(token: str, action: str) -> dict[str, str | bool]:
    """Accept one nudge from glasses that already photographed this account's QR."""
    act = normalize_remote_action(action)
    if not act:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown remote action")
    owner = await _bound_owner_id(token)
    if owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Glasses are not bound")
    if not push_remote_action(get_redis(), owner, act):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Remote queue is unavailable")
    await publish_glasses_event(owner, "remote")
    return {"ok": True, "display": REMOTE_DISPLAY[act]}


async def drain_glasses_remote(user_id: int) -> dict[str, list[str]]:
    """Actions waiting for the signed-in editor. An empty list is the idle case."""
    return {"actions": take_remote_actions(get_redis(), int(user_id))}
