"""Persist Kitty live context to Redis for multi-worker visibility and hydrate support."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional, Tuple

from redis.exceptions import RedisError

from services.infrastructure.monitoring.ws_metrics import (
    record_kitty_command_context_merge,
    record_kitty_redis_persist,
    record_ws_coalesce_hit,
)
from services.kitty.infra.desktop.kitty_mobile_active import mark_kitty_mobile_active
from services.kitty.infra.redis.kitty_redis_keys import (
    kitty_live_spec_key,
    kitty_redis_ttl_seconds,
    kitty_scope_owner_key,
    kitty_sessionmeta_key,
    kitty_ws_refcount_key,
)
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_DEBOUNCE_SEC = 0.08
_coalesce_lock = asyncio.Lock()
_coalesce_tasks: Dict[str, asyncio.Task] = {}
_coalesce_pending: Dict[str, Tuple[int, Dict[str, Any], str, str, Optional[str], Optional[str]]] = {}


class _VoiceSessionGetterSlot:
    """Holds optional voice-session getter without module-level ``global`` assignments."""

    __slots__ = ("getter",)

    def __init__(self) -> None:
        self.getter: Optional[Any] = None


_VOICE_SESSION_GETTER = _VoiceSessionGetterSlot()


def configure_voice_session_getter(getter: Any) -> None:
    """Avoid services→routers import cycles: set ``get_voice_session`` from ``session_ops`` startup."""
    _VOICE_SESSION_GETTER.getter = getter


def _get_voice_session_coalesce(voice_sid: str) -> Optional[Dict[str, Any]]:
    getter = _VOICE_SESSION_GETTER.getter
    if getter is not None:
        return getter(voice_sid)
    from services.kitty.session.ops import get_voice_session

    return get_voice_session(voice_sid)


async def upsert_kitty_redis_session(
    ws_session_id: str,
    user_id: int,
    *,
    active_diagram_library_id: Optional[str],
    live_payload: Dict[str, Any],
    client_lane: Optional[str] = None,
    preserve_mobile_lane: bool = True,
) -> Optional[int]:
    """Write session meta + live spec; refresh TTL. Returns live ``updated_at`` epoch or ``None``."""
    redis = get_async_redis()
    if redis is None:
        return None
    ttl = kitty_redis_ttl_seconds()
    now = int(time.time())
    meta = {
        "user_id": user_id,
        "updated_at": now,
        "active_diagram_library_id": active_diagram_library_id,
    }
    if client_lane == "mobile":
        meta["client_lane"] = "mobile"
    live_payload = {**live_payload, "updated_at": now}
    try:
        meta_key = kitty_sessionmeta_key(ws_session_id)
        live_key = kitty_live_spec_key(ws_session_id)
        owner_key = kitty_scope_owner_key(ws_session_id)
        if client_lane != "mobile" and preserve_mobile_lane:
            try:
                raw_prev = await redis.get(meta_key)
                if raw_prev:
                    text_prev = raw_prev.decode("utf-8") if isinstance(raw_prev, bytes) else raw_prev
                    prev = json.loads(text_prev)
                    if isinstance(prev, dict) and prev.get("client_lane") == "mobile":
                        if int(prev.get("user_id", -1)) == user_id:
                            meta["client_lane"] = "mobile"
            except (RedisError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
                pass
        async with redis.pipeline(transaction=False) as pipe:
            pipe.set(meta_key, json.dumps(meta, ensure_ascii=False), ex=ttl)
            pipe.set(live_key, json.dumps(live_payload, ensure_ascii=False), ex=ttl)
            pipe.set(owner_key, str(int(user_id)), ex=ttl)
            await pipe.execute()
        if client_lane == "mobile":
            await mark_kitty_mobile_active(user_id, ws_session_id)
        record_kitty_redis_persist()
        return now
    except (RedisError, TypeError, ValueError) as exc:
        logger.warning("[KittyRedis] upsert failed ws=%s: %s", ws_session_id, exc)
        return None


async def persist_kitty_live_for_ws(
    ws_session_id: str,
    user_id: int,
    merged_context: Dict[str, Any],
    diagram_type: str,
    active_panel: str,
    *,
    client_lane: Optional[str] = None,
    preserve_mobile_lane: bool = True,
) -> Optional[int]:
    """Map VoiceContext merge to Redis live_payload; returns ``updated_at`` or ``None``."""
    lib = merged_context.get("diagram_library_id")
    lib_str = lib if isinstance(lib, str) and lib.strip() else None
    return await upsert_kitty_redis_session(
        ws_session_id,
        user_id,
        active_diagram_library_id=lib_str,
        client_lane=client_lane,
        preserve_mobile_lane=preserve_mobile_lane,
        live_payload={
            "diagram_type": diagram_type,
            "active_panel": active_panel,
            "diagram_data": merged_context.get("diagram_data") or {},
            "selected_nodes": merged_context.get("selected_nodes") or [],
            "diagram_library_id": lib_str,
            "diagram_display_title": merged_context.get("diagram_display_title"),
        },
    )


async def load_kitty_live_context(ws_session_id: str) -> Optional[Dict[str, Any]]:
    """Read decoded ``kitty:live_spec`` JSON, or ``None``."""
    redis = get_async_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(kitty_live_spec_key(ws_session_id))
        if not raw:
            return None
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except (RedisError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.debug("[KittyRedis] load live failed ws=%s: %s", ws_session_id, exc)
        return None


async def kitty_mobile_indicator_armed_for_user(ws_session_id: str, user_id: int) -> bool:
    """
    True when Kitty sessionmeta exists, belongs to ``user_id``, and was started from
    a mobile ``client_lane`` (phone mic session), for desktop ``mobile_lane`` polling.
    """
    redis = get_async_redis()
    if redis is None:
        return False
    try:
        raw = await redis.get(kitty_sessionmeta_key(ws_session_id))
        if not raw:
            return False
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        meta = json.loads(text)
        if not isinstance(meta, dict):
            return False
        if int(meta.get("user_id", -1)) != user_id:
            return False
        return meta.get("client_lane") == "mobile"
    except (RedisError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.debug("[KittyRedis] sessionmeta read failed ws=%s: %s", ws_session_id, exc)
        return False


async def kitty_sessionmeta_active_for_user(ws_session_id: str, user_id: int) -> bool:
    """True if ``kitty:sessionmeta`` exists and belongs to ``user_id``."""
    redis = get_async_redis()
    if redis is None:
        return False
    try:
        raw = await redis.get(kitty_sessionmeta_key(ws_session_id))
        if not raw:
            return False
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        meta = json.loads(text)
        if not isinstance(meta, dict):
            return False
        return int(meta.get("user_id", -1)) == user_id
    except (RedisError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.debug("[KittyRedis] sessionmeta read failed ws=%s: %s", ws_session_id, exc)
        return False


async def fetch_kitty_sessionmeta_for_user(ws_session_id: str, user_id: int) -> Optional[Dict[str, Any]]:
    """Return sessionmeta dict if it exists and belongs to ``user_id``, else ``None``."""
    redis = get_async_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(kitty_sessionmeta_key(ws_session_id))
        if not raw:
            return None
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        meta = json.loads(text)
        if not isinstance(meta, dict):
            return None
        if int(meta.get("user_id", -1)) != user_id:
            return None
        return meta
    except (RedisError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.debug("[KittyRedis] sessionmeta fetch failed ws=%s: %s", ws_session_id, exc)
        return None


async def delete_kitty_redis_session(ws_session_id: str, *, user_id: Optional[int] = None) -> None:
    """
    Remove Kitty session keys.

    When ``user_id`` is set, only delete if sessionmeta's user_id matches
    (prevents cross-user cleanup abuse).
    """
    redis = get_async_redis()
    if redis is None:
        return
    meta_key = kitty_sessionmeta_key(ws_session_id)
    live_key = kitty_live_spec_key(ws_session_id)
    owner_key = kitty_scope_owner_key(ws_session_id)
    refcount_key = kitty_ws_refcount_key(ws_session_id)
    try:
        if user_id is not None:
            raw = await redis.get(meta_key)
            if raw:
                try:
                    meta = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
                    if int(meta.get("user_id", -1)) != user_id:
                        logger.warning(
                            "[KittyRedis] delete denied ws=%s expected_user=%s",
                            ws_session_id,
                            user_id,
                        )
                        return
                except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
                    pass
        await redis.delete(meta_key, live_key, owner_key, refcount_key)
    except (RedisError, TypeError) as exc:
        logger.debug("[KittyRedis] delete failed ws=%s: %s", ws_session_id, exc)


async def _coalesce_worker(ws_session_id: str) -> None:
    """Debounce: sleep, pop latest pending payload, persist; loop until idle."""
    try:
        while True:
            await asyncio.sleep(_DEBOUNCE_SEC)
            async with _coalesce_lock:
                payload = _coalesce_pending.pop(ws_session_id, None)
                if not payload:
                    cur = asyncio.current_task()
                    if _coalesce_tasks.get(ws_session_id) is cur:
                        _coalesce_tasks.pop(ws_session_id, None)
                    return
            user_id, merged_ctx, diagram_type, active_panel, voice_sid, client_lane = payload
            ts = await persist_kitty_live_for_ws(
                ws_session_id,
                user_id,
                merged_ctx,
                diagram_type,
                active_panel,
                client_lane=client_lane,
            )
            if voice_sid and ts is not None:
                sess = _get_voice_session_coalesce(voice_sid)
                if sess is not None:
                    sess["_kitty_redis_seen_ts"] = ts
    except asyncio.CancelledError:
        async with _coalesce_lock:
            cur = asyncio.current_task()
            if _coalesce_tasks.get(ws_session_id) is cur:
                _coalesce_tasks.pop(ws_session_id, None)
        raise


async def schedule_persist_kitty_live_debounced(
    ws_session_id: str,
    user_id: int,
    merged_context: Dict[str, Any],
    diagram_type: str,
    active_panel: str,
    *,
    voice_session_id: Optional[str] = None,
) -> None:
    """Coalesce bursty ``context_update`` Redis writes per ``ws_session_id``."""
    lane: Optional[str] = None
    if voice_session_id:
        sess = _get_voice_session_coalesce(voice_session_id)
        if sess is not None:
            raw_lane = sess.get("_kitty_client_lane")
            if raw_lane == "mobile":
                lane = "mobile"
    async with _coalesce_lock:
        _coalesce_pending[ws_session_id] = (
            user_id,
            merged_context,
            diagram_type,
            active_panel,
            voice_session_id,
            lane,
        )
        existing = _coalesce_tasks.get(ws_session_id)
        if existing and not existing.done():
            record_ws_coalesce_hit("kitty_persist")
            return
        _coalesce_tasks[ws_session_id] = asyncio.create_task(_coalesce_worker(ws_session_id))


def apply_redis_live_to_voice_session(session: Dict[str, Any], live: Dict[str, Any]) -> None:
    """Last-write-wins merge from Redis ``live_spec`` into in-memory voice session."""
    rts = int(live.get("updated_at") or 0)
    seen = int(session.get("_kitty_redis_seen_ts") or 0)
    if rts <= seen:
        return
    ctx = dict(session.get("context") or {})
    dd = live.get("diagram_data")
    if isinstance(dd, dict):
        ctx["diagram_data"] = dd
    sn = live.get("selected_nodes")
    if isinstance(sn, list):
        ctx["selected_nodes"] = sn
    dt = live.get("diagram_type")
    if isinstance(dt, str) and dt:
        ctx["diagram_type"] = dt
    dlib = live.get("diagram_library_id")
    if isinstance(dlib, str) and dlib:
        ctx["diagram_library_id"] = dlib
    title = live.get("diagram_display_title")
    if isinstance(title, str):
        ctx["diagram_display_title"] = title
    ap = live.get("active_panel")
    if isinstance(ap, str) and ap:
        ctx["active_panel"] = ap
    session["context"] = ctx
    if isinstance(dt, str) and dt:
        session["diagram_type"] = dt
    session["_kitty_redis_seen_ts"] = rts
    record_kitty_command_context_merge()
