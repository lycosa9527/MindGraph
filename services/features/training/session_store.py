"""
Redis session document for org training follow.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Optional

from services.features.training.constants import (
    ACTIVE_STATES,
    INSTRUCTOR_HEARTBEAT_STALE_SECONDS,
    INSTRUCTOR_KEY,
    ORG_SESSION_KEY,
    SESSION_HARD_TTL_SECONDS,
    STATE_ENDED,
    STATE_LIVE,
    STATE_PAUSED,
    STEER_MIN_INTERVAL_SECONDS,
    TOMBSTONE_TTL_SECONDS,
)
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)


class TrainingSessionError(Exception):
    """Domain error for training session transitions."""

    def __init__(
        self,
        code: str,
        message: str,
        extras: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.extras = extras or {}


def _org_key(org_id: int) -> str:
    return ORG_SESSION_KEY.format(org_id=int(org_id))


def _instructor_key(user_id: int) -> str:
    return INSTRUCTOR_KEY.format(user_id=int(user_id))


def _now() -> float:
    return time.time()


def _decode(raw: Any) -> Optional[dict[str, Any]]:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


async def get_session_raw(org_id: int) -> Optional[dict[str, Any]]:
    """Load the org session document without applying hard TTL."""
    try:
        redis = get_async_redis()
        if redis is None:
            return None
        return _decode(await redis.get(_org_key(org_id)))
    except REDIS_ERRORS as exc:
        logger.debug("[Training] get_session_raw failed: %s", exc)
        return None


async def get_session(org_id: int) -> Optional[dict[str, Any]]:
    """Load the org session document, honoring hard TTL."""
    parsed = await get_session_raw(org_id)
    if parsed is None:
        return None
    expires_at = float(parsed.get("expires_at") or 0)
    if expires_at and _now() >= expires_at and parsed.get("state") != STATE_ENDED:
        await end_session(org_id, tombstone=True)
        return await get_session_raw(org_id)
    return parsed


async def get_instructor_pointer(user_id: int) -> Optional[dict[str, Any]]:
    """Org + session the instructor currently hosts."""
    try:
        redis = get_async_redis()
        if redis is None:
            return None
        return _decode(await redis.get(_instructor_key(user_id)))
    except REDIS_ERRORS as exc:
        logger.debug("[Training] get_instructor_pointer failed: %s", exc)
        return None


async def _write_session(session: dict[str, Any], ttl: int) -> None:
    redis = get_async_redis()
    if redis is None:
        raise TrainingSessionError("redis_unavailable", "Redis is not available")
    org_id = int(session["org_id"])
    instructor_id = int(session["instructor_id"])
    pointer = json.dumps(
        {"org_id": org_id, "session_id": session["session_id"]},
        separators=(",", ":"),
    )
    payload = json.dumps(session, separators=(",", ":"))
    async with redis.pipeline(transaction=False) as pipe:
        pipe.set(_org_key(org_id), payload, ex=ttl)
        if session.get("state") in ACTIVE_STATES:
            pipe.set(_instructor_key(instructor_id), pointer, ex=ttl)
        await pipe.execute()


async def start_session(
    *,
    org_id: int,
    instructor_id: int,
    instructor_name: str,
    confirm_teacher_total: int,
) -> dict[str, Any]:
    """Create a live session or raise if org/instructor already hosts one."""
    existing = await get_session(org_id)
    if existing is not None and existing.get("state") in ACTIVE_STATES:
        raise TrainingSessionError(
            "org_busy",
            "This school already has an active training session",
            extras={
                "instructor_name": existing.get("instructor_name"),
                "instructor_id": existing.get("instructor_id"),
                "started_at": existing.get("started_at"),
                "session_id": existing.get("session_id"),
            },
        )
    hosted = await get_instructor_pointer(instructor_id)
    if hosted is not None:
        hosted_org = int(hosted.get("org_id") or 0)
        hosted_session = await get_session(hosted_org)
        if hosted_session is not None and hosted_session.get("state") in ACTIVE_STATES:
            raise TrainingSessionError(
                "instructor_busy",
                "You already host a training session",
            )
    now = _now()
    session = {
        "session_id": str(uuid.uuid4()),
        "org_id": int(org_id),
        "instructor_id": int(instructor_id),
        "instructor_name": instructor_name,
        "state": STATE_LIVE,
        "seq": 1,
        "diagram_type": None,
        "topic_options": [],
        "started_at": now,
        "updated_at": now,
        "expires_at": now + SESSION_HARD_TTL_SECONDS,
        "instructor_seen_at": now,
        "confirm_teacher_count": int(confirm_teacher_total),
        "last_steer_at": 0.0,
        "taken_over_from": None,
    }
    await _write_session(session, SESSION_HARD_TTL_SECONDS)
    return session


async def bump_and_save(
    session: dict[str, Any],
    *,
    extra: Optional[dict[str, Any]] = None,
    rate_limit_steer: bool = False,
) -> dict[str, Any]:
    """Increment seq, merge extras, persist."""
    now = _now()
    if rate_limit_steer:
        last = float(session.get("last_steer_at") or 0)
        if now - last < STEER_MIN_INTERVAL_SECONDS:
            raise TrainingSessionError("rate_limited", "Steer too quickly")
        session["last_steer_at"] = now
    session["seq"] = int(session.get("seq") or 0) + 1
    session["updated_at"] = now
    if extra:
        session.update(extra)
    remaining = max(int(float(session.get("expires_at") or now) - now), 1)
    await _write_session(session, remaining)
    return session


async def heartbeat(org_id: int, instructor_id: int) -> Optional[dict[str, Any]]:
    """Refresh instructor_seen_at when the owner is still hosting."""
    session = await get_session(org_id)
    if session is None or session.get("state") not in ACTIVE_STATES:
        return None
    if int(session.get("instructor_id") or 0) != int(instructor_id):
        raise TrainingSessionError("not_owner", "Only the session instructor may heartbeat")
    session["instructor_seen_at"] = _now()
    remaining = max(int(float(session.get("expires_at") or _now()) - _now()), 1)
    await _write_session(session, remaining)
    return session


async def maybe_auto_pause(session: dict[str, Any]) -> dict[str, Any]:
    """Pause a live session when the instructor heartbeat is stale."""
    if session.get("state") != STATE_LIVE:
        return session
    seen = float(session.get("instructor_seen_at") or 0)
    if _now() - seen < INSTRUCTOR_HEARTBEAT_STALE_SECONDS:
        return session
    return await bump_and_save(session, extra={"state": STATE_PAUSED})


async def pause_session(org_id: int, instructor_id: int) -> dict[str, Any]:
    """Explicit pause by the owner."""
    session = await _require_owner_active(org_id, instructor_id)
    if session.get("state") == STATE_PAUSED:
        return session
    return await bump_and_save(session, extra={"state": STATE_PAUSED})


async def resume_session(org_id: int, instructor_id: int) -> dict[str, Any]:
    """Resume a paused session."""
    session = await _require_owner_active(org_id, instructor_id)
    if session.get("state") == STATE_LIVE:
        return session
    return await bump_and_save(
        session,
        extra={"state": STATE_LIVE, "instructor_seen_at": _now()},
    )


async def takeover_session(org_id: int, new_instructor_id: int, new_name: str) -> dict[str, Any]:
    """Transfer ownership, keeping seq and snapshot."""
    session = await get_session(org_id)
    if session is None or session.get("state") not in ACTIVE_STATES:
        raise TrainingSessionError("not_found", "No active training session")
    old_id = int(session.get("instructor_id") or 0)
    if old_id == int(new_instructor_id):
        return session
    hosted = await get_instructor_pointer(new_instructor_id)
    if hosted is not None:
        other = await get_session(int(hosted.get("org_id") or 0))
        if other is not None and other.get("state") in ACTIVE_STATES:
            if str(other.get("session_id")) != str(session.get("session_id")):
                raise TrainingSessionError(
                    "instructor_busy",
                    "You already host a training session",
                )
    try:
        redis = get_async_redis()
        if redis is not None and old_id:
            await redis.delete(_instructor_key(old_id))
    except REDIS_ERRORS as exc:
        logger.debug("[Training] takeover delete old pointer failed: %s", exc)
    return await bump_and_save(
        session,
        extra={
            "instructor_id": int(new_instructor_id),
            "instructor_name": new_name,
            "taken_over_from": old_id,
            "instructor_seen_at": _now(),
            "state": STATE_LIVE,
        },
    )


async def end_session(org_id: int, *, tombstone: bool = True) -> Optional[dict[str, Any]]:
    """End the org session and drop the instructor pointer."""
    session = await get_session_raw(org_id)
    if session is None:
        return None
    instructor_id = int(session.get("instructor_id") or 0)
    session["state"] = STATE_ENDED
    session["seq"] = int(session.get("seq") or 0) + 1
    session["updated_at"] = _now()
    try:
        redis = get_async_redis()
        if redis is None:
            return session
        if instructor_id:
            await redis.delete(_instructor_key(instructor_id))
        if tombstone:
            await _write_session(session, TOMBSTONE_TTL_SECONDS)
        else:
            await redis.delete(_org_key(org_id))
    except REDIS_ERRORS as exc:
        logger.debug("[Training] end_session failed: %s", exc)
        raise TrainingSessionError("redis_unavailable", "Redis is not available") from exc
    return session


async def _require_owner_active(org_id: int, instructor_id: int) -> dict[str, Any]:
    session = await get_session(org_id)
    if session is None or session.get("state") not in ACTIVE_STATES:
        raise TrainingSessionError("not_found", "No active training session")
    if int(session.get("instructor_id") or 0) != int(instructor_id):
        raise TrainingSessionError("not_owner", "Only the session instructor may do this")
    return session


async def require_owner_active(org_id: int, instructor_id: int) -> dict[str, Any]:
    """Public owner+active guard."""
    return await _require_owner_active(org_id, instructor_id)
