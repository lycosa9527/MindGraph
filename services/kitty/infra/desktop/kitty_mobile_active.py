"""User-level Redis signal: which diagram scopes have mobile-lane Kitty active."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from redis.exceptions import RedisError, WatchError

from services.kitty.infra.desktop.kitty_desktop_wake_fanout import publish_kitty_desktop_wake
from services.kitty.infra.redis.kitty_redis_keys import kitty_mobile_active_key, kitty_redis_ttl_seconds
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_WATCH_MAX_ATTEMPTS = 5
_WATCH_RETRY_DELAY_SEC = 0.02

_INACTIVE_BODY: Dict[str, Any] = {
    "active": False,
    "scopes": [],
    "primary_scope": None,
}


def _normalize_scope(scope: str) -> Optional[str]:
    """Normalize scope."""
    text = str(scope).strip()
    if not text:
        return None
    return text


def _decode_payload(raw: Any) -> Optional[Dict[str, Any]]:
    """Decode payload."""
    if raw is None:
        return None
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        return data
    except (TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _scopes_from_payload(data: Dict[str, Any]) -> List[str]:
    """Scopes from payload."""
    raw = data.get("scopes")
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for item in raw:
        if isinstance(item, str):
            norm = _normalize_scope(item)
            if norm is not None and norm not in out:
                out.append(norm)
    return out


async def _emit_desktop_wake(user_id: int, mobile_state: Dict[str, Any]) -> None:
    """Emit desktop wake."""
    await publish_kitty_desktop_wake(int(user_id), mobile_state)


async def mark_kitty_mobile_active(user_id: int, scope: str) -> None:
    """Record an active mobile-lane Kitty session for ``scope``; refresh TTL."""
    norm_scope = _normalize_scope(scope)
    if norm_scope is None:
        return
    redis = get_async_redis()
    if redis is None:
        return
    key = kitty_mobile_active_key(int(user_id))
    ttl = kitty_redis_ttl_seconds()
    now = int(time.time())
    wake_payload: Optional[Dict[str, Any]] = None
    for attempt in range(_WATCH_MAX_ATTEMPTS):
        try:
            async with redis.pipeline(transaction=True) as pipe:
                await pipe.watch(key)
                raw_get = await pipe.get(key)
                data = _decode_payload(raw_get) or {}
                scopes = _scopes_from_payload(data)
                if norm_scope in scopes:
                    scopes.remove(norm_scope)
                scopes.append(norm_scope)
                stored = {
                    "scopes": scopes,
                    "primary_scope": norm_scope,
                    "updated_at": now,
                }
                pipe.multi()
                pipe.set(key, json.dumps(stored, ensure_ascii=False), ex=ttl)
                await pipe.execute()
            wake_payload = {
                "active": True,
                "scopes": scopes,
                "primary_scope": norm_scope,
            }
            break
        except WatchError:
            if attempt < _WATCH_MAX_ATTEMPTS - 1:
                await asyncio.sleep(_WATCH_RETRY_DELAY_SEC)
            continue
        except (RedisError, TypeError, ValueError) as exc:
            logger.warning(
                "[KittyMobileActive] mark failed user=%s scope=%s: %s",
                user_id,
                scope,
                exc,
            )
            return
    if wake_payload is None:
        logger.warning(
            "[KittyMobileActive] mark watch retries exhausted user=%s scope=%s",
            user_id,
            scope,
        )
        return
    await _emit_desktop_wake(user_id, wake_payload)


async def clear_kitty_mobile_scope(user_id: int, scope: str) -> None:
    """Remove ``scope`` from the user's mobile-active set; delete key when empty."""
    norm_scope = _normalize_scope(scope)
    if norm_scope is None:
        return
    redis = get_async_redis()
    if redis is None:
        return
    key = kitty_mobile_active_key(int(user_id))
    ttl = kitty_redis_ttl_seconds()
    wake_payload: Optional[Dict[str, Any]] = None
    for attempt in range(_WATCH_MAX_ATTEMPTS):
        try:
            async with redis.pipeline(transaction=True) as pipe:
                await pipe.watch(key)
                raw_get = await pipe.get(key)
                data = _decode_payload(raw_get)
                if not data:
                    return
                scopes = _scopes_from_payload(data)
                if norm_scope not in scopes:
                    return
                scopes.remove(norm_scope)
                if not scopes:
                    pipe.multi()
                    pipe.delete(key)
                    await pipe.execute()
                    wake_payload = dict(_INACTIVE_BODY)
                    break
                primary = data.get("primary_scope")
                primary_norm = _normalize_scope(primary) if isinstance(primary, str) else None
                if primary_norm == norm_scope or primary_norm not in scopes:
                    primary_norm = scopes[-1]
                stored = {
                    "scopes": scopes,
                    "primary_scope": primary_norm,
                    "updated_at": int(time.time()),
                }
                pipe.multi()
                pipe.set(key, json.dumps(stored, ensure_ascii=False), ex=ttl)
                await pipe.execute()
                wake_payload = {
                    "active": True,
                    "scopes": scopes,
                    "primary_scope": primary_norm,
                }
                break
        except WatchError:
            if attempt < _WATCH_MAX_ATTEMPTS - 1:
                await asyncio.sleep(_WATCH_RETRY_DELAY_SEC)
            continue
        except (RedisError, TypeError, ValueError) as exc:
            logger.warning(
                "[KittyMobileActive] clear failed user=%s scope=%s: %s",
                user_id,
                scope,
                exc,
            )
            return
    if wake_payload is None:
        logger.warning(
            "[KittyMobileActive] clear watch retries exhausted user=%s scope=%s",
            user_id,
            scope,
        )
        return
    await _emit_desktop_wake(user_id, wake_payload)


async def read_kitty_mobile_active(user_id: int) -> Dict[str, Any]:
    """Return ``{ active, scopes, primary_scope }`` for desktop poll gating."""
    redis = get_async_redis()
    if redis is None:
        return dict(_INACTIVE_BODY)
    key = kitty_mobile_active_key(int(user_id))
    try:
        raw = await redis.get(key)
        data = _decode_payload(raw)
        if not data:
            return dict(_INACTIVE_BODY)
        scopes = _scopes_from_payload(data)
        if not scopes:
            return dict(_INACTIVE_BODY)
        primary = data.get("primary_scope")
        primary_norm = _normalize_scope(primary) if isinstance(primary, str) else None
        if primary_norm is None or primary_norm not in scopes:
            primary_norm = scopes[-1]
        return {
            "active": True,
            "scopes": scopes,
            "primary_scope": primary_norm,
        }
    except (RedisError, TypeError, ValueError) as exc:
        logger.warning("[KittyMobileActive] read failed user=%s: %s", user_id, exc)
        return dict(_INACTIVE_BODY)
