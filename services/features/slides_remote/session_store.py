"""
Redis document + command list for one user's 演讲模式 clicker.

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

from services.features.slides_remote.constants import (
    COMMAND_ACTIONS,
    COMMAND_KEY,
    COMMAND_QUEUE_MAX,
    DIAGRAM_ID_MAX,
    SESSION_TTL_SECONDS,
    STATE_ENDED,
    STATE_IDLE,
    STATE_LIVE,
    TITLE_MAX,
    TRAVERSAL_MODES,
    USER_KEY,
)
from services.features.slides_remote.wake_fanout import (
    publish_slides_command_pending,
    publish_slides_snapshot_view,
)
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import JSON_PARSE_ERRORS, REDIS_ERRORS

logger = logging.getLogger(__name__)


class SlideRemoteError(Exception):
    """Domain error for slide-remote transitions."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _user_key(user_id: int) -> str:
    return USER_KEY.format(user_id=int(user_id))


def _command_key(user_id: int) -> str:
    return COMMAND_KEY.format(user_id=int(user_id))


def _decode(raw: Any) -> Optional[dict[str, Any]]:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = json.loads(raw)
    except JSON_PARSE_ERRORS:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _clip(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit]


def _as_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _as_bool(value: Any, fallback: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    return fallback


def idle_snapshot() -> dict[str, Any]:
    """Watch-facing empty document when no live 演讲模式 exists."""
    return {
        "state": STATE_IDLE,
        "session_id": "",
        "diagram_id": "",
        "title": "",
        "slide_index": 0,
        "slide_count": 0,
        "traversal": "firstLevel",
        "autoplay": False,
        "can_prev": False,
        "can_next": False,
        "seq": 0,
    }


def public_snapshot(session: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Strip heartbeat internals for HTTP."""
    if session is None:
        return idle_snapshot()
    view = idle_snapshot()
    view["state"] = str(session.get("state") or STATE_IDLE)
    view["session_id"] = str(session.get("session_id") or "")
    view["diagram_id"] = str(session.get("diagram_id") or "")
    view["title"] = str(session.get("title") or "")
    view["slide_index"] = max(0, _as_int(session.get("slide_index"), 0))
    view["slide_count"] = max(0, _as_int(session.get("slide_count"), 0))
    traversal = str(session.get("traversal") or "firstLevel")
    view["traversal"] = traversal if traversal in TRAVERSAL_MODES else "firstLevel"
    view["autoplay"] = _as_bool(session.get("autoplay"), False)
    view["can_prev"] = _as_bool(session.get("can_prev"), False)
    view["can_next"] = _as_bool(session.get("can_next"), False)
    view["seq"] = max(0, _as_int(session.get("seq"), 0))
    if view["state"] != STATE_LIVE or not view["session_id"]:
        view["state"] = STATE_IDLE
    return view


async def _require_redis() -> Any:
    redis = get_async_redis()
    if redis is None:
        raise SlideRemoteError("redis_unavailable", "Redis is not available")
    return redis


async def touch_session(user_id: int) -> bool:
    """Refresh Redis TTL when a desktop socket is still holding the room."""
    try:
        redis = get_async_redis()
        if redis is None:
            return False
        key = _user_key(user_id)
        if not await redis.exists(key):
            return False
        await redis.expire(key, SESSION_TTL_SECONDS)
        await redis.expire(_command_key(user_id), SESSION_TTL_SECONDS)
        return True
    except REDIS_ERRORS as exc:
        logger.debug("[SlideRemote] touch_session failed: %s", exc)
        return False


async def get_session(user_id: int) -> Optional[dict[str, Any]]:
    """Load the live document. Readers never write."""
    try:
        redis = get_async_redis()
        if redis is None:
            return None
        return _decode(await redis.get(_user_key(user_id)))
    except REDIS_ERRORS as exc:
        logger.debug("[SlideRemote] get_session failed: %s", exc)
        return None


def _hud_key(session: Optional[dict[str, Any]]) -> tuple[Any, ...]:
    """HUD fields the watch paints. Seq / heartbeat are not part of the face."""
    view = public_snapshot(session)
    return (
        view["state"],
        view["session_id"],
        view["diagram_id"],
        view["title"],
        view["slide_index"],
        view["slide_count"],
        view["traversal"],
        view["autoplay"],
        view["can_prev"],
        view["can_next"],
    )


def _apply_fields(session: dict[str, Any], fields: dict[str, Any]) -> None:
    session["diagram_id"] = _clip(fields.get("diagram_id"), DIAGRAM_ID_MAX)
    session["title"] = _clip(fields.get("title"), TITLE_MAX)
    session["slide_index"] = max(0, _as_int(fields.get("slide_index"), 0))
    session["slide_count"] = max(0, _as_int(fields.get("slide_count"), 0))
    traversal = str(fields.get("traversal") or session.get("traversal") or "firstLevel")
    session["traversal"] = traversal if traversal in TRAVERSAL_MODES else "firstLevel"
    session["autoplay"] = _as_bool(fields.get("autoplay"), False)
    session["can_prev"] = _as_bool(fields.get("can_prev"), False)
    session["can_next"] = _as_bool(fields.get("can_next"), False)


async def upsert_session(user_id: int, fields: dict[str, Any]) -> dict[str, Any]:
    """Create or refresh the live snapshot. Desktop owns the room."""
    redis = await _require_redis()
    existing = await get_session(user_id)
    now = time.time()
    if existing and str(existing.get("state")) == STATE_LIVE:
        session = dict(existing)
        session["seq"] = max(0, _as_int(existing.get("seq"), 0)) + 1
    else:
        session = {
            "state": STATE_LIVE,
            "session_id": str(uuid.uuid4()),
            "user_id": int(user_id),
            "seq": 1,
        }
    session["state"] = STATE_LIVE
    session["user_id"] = int(user_id)
    session["heartbeat_at"] = now
    _apply_fields(session, fields)
    changed = _hud_key(existing) != _hud_key(session)
    payload = json.dumps(session, separators=(",", ":"))
    await redis.set(_user_key(user_id), payload, ex=SESSION_TTL_SECONDS)
    await redis.expire(_command_key(user_id), SESSION_TTL_SECONDS)
    if changed:
        await publish_slides_snapshot_view(user_id, public_snapshot(session))
    return session


async def end_session(user_id: int) -> None:
    """Drop the snapshot and queued clicks."""
    try:
        redis = get_async_redis()
        if redis is None:
            return
        await redis.delete(_user_key(user_id), _command_key(user_id))
    except REDIS_ERRORS as exc:
        logger.debug("[SlideRemote] end_session failed: %s", exc)
        return
    await publish_slides_snapshot_view(user_id, public_snapshot(None))


def normalize_command(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a watch click into a stored command row."""
    action = str(payload.get("action") or "").strip()
    if action not in COMMAND_ACTIONS:
        raise SlideRemoteError("bad_action", "Unknown slide remote action")
    row: dict[str, Any] = {"id": str(uuid.uuid4()), "action": action}
    if action == "autoplay" and "on" in payload:
        row["on"] = _as_bool(payload.get("on"), False)
    if action == "traversal":
        mode = str(payload.get("mode") or "").strip()
        if mode not in TRAVERSAL_MODES:
            raise SlideRemoteError("bad_traversal", "Traversal must be firstLevel or deep")
        row["mode"] = mode
    if action == "start":
        diagram_id = _clip(payload.get("diagram_id"), DIAGRAM_ID_MAX)
        if not diagram_id:
            raise SlideRemoteError("bad_diagram", "Start needs a diagram")
        row["diagram_id"] = diagram_id
    return row


async def enqueue_command(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Append a click. Start works before 演讲模式; other actions need a live room."""
    row = normalize_command(payload)
    if row["action"] != "start":
        session = await get_session(user_id)
        if session is None or str(session.get("state")) != STATE_LIVE:
            raise SlideRemoteError("not_found", "No live slide session")
    redis = await _require_redis()
    key = _command_key(user_id)
    await redis.rpush(key, json.dumps(row, separators=(",", ":")))
    await redis.ltrim(key, -COMMAND_QUEUE_MAX, -1)
    await redis.expire(key, SESSION_TTL_SECONDS)
    await publish_slides_command_pending(user_id)
    return row


async def drain_commands(user_id: int) -> list[dict[str, Any]]:
    """Pop queued clicks for the desktop tab, including Start before a room exists."""
    try:
        redis = get_async_redis()
        if redis is None:
            return []
        key = _command_key(user_id)
        items: list[dict[str, Any]] = []
        for _ in range(COMMAND_QUEUE_MAX):
            raw = await redis.lpop(key)
            parsed = _decode(raw)
            if parsed is None:
                break
            items.append(parsed)
        return items
    except REDIS_ERRORS as exc:
        logger.debug("[SlideRemote] drain_commands failed: %s", exc)
        return []


def ended_snapshot() -> dict[str, Any]:
    """HTTP body after the desktop leaves 演讲模式."""
    view = idle_snapshot()
    view["state"] = STATE_ENDED
    return view
