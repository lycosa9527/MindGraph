"""OAuth access token for enterprise internal apps (cached in Redis).

Thundering-herd prevention
--------------------------
On a cold cache (server restart or TTL expiry), many concurrent requests for the
same org would all miss Redis and fire parallel DingTalk OAuth POSTs.  A per-org
``asyncio.Lock`` keyed by the cache key serialises these so only the first caller
fetches a fresh token; all others wait and then read it from the cache.

In-process locks are stored in an LRU map capped by ``MINDBOT_OAUTH_LOCK_MAP_MAX``
(default 2048) so worker memory stays bounded when many distinct org credentials
appear over the process lifetime.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import logging
import re
from collections import OrderedDict
from typing import Any, Optional

import aiohttp

from services.mindbot.infra.http_client import get_dingtalk_api_session
from services.mindbot.platforms.dingtalk.api.constants import DING_API_BASE, PATH_OAUTH_ACCESS_TOKEN, TOKEN_TTL_SECONDS
from services.mindbot.infra.redis_async import redis_delete, redis_get, redis_set_ttl
from services.redis.redis_client import is_redis_available
from utils.env_helpers import env_int

logger = logging.getLogger(__name__)

_token_fetch_locks: "OrderedDict[str, asyncio.Lock]" = OrderedDict()

_SENSITIVE_PATTERN = re.compile(
    r'("(?:appSecret|appKey|accessToken|access_token|secret|password)")\s*:\s*"[^"]{4,}"',
    re.IGNORECASE,
)


def _sanitize_oauth_snippet(body_txt: str, max_len: int = 400) -> str:
    """Return a truncated, credential-redacted snippet safe for WARNING logs."""
    snippet = body_txt[:max_len]
    return _SENSITIVE_PATTERN.sub(r'\1: "***"', snippet)


@functools.cache
def _oauth_lock_map_max_entries() -> int:
    """Upper bound on in-process OAuth thundering-herd locks (LRU eviction)."""
    return max(2, min(65536, env_int("MINDBOT_OAUTH_LOCK_MAP_MAX", 2048)))


def oauth_lock_map_size() -> int:
    """Return current size of the per-credential asyncio.Lock map (for metrics)."""
    return len(_token_fetch_locks)


def oauth_lock_map_max_configured() -> int:
    """Configured maximum entries before LRU eviction (see ``MINDBOT_OAUTH_LOCK_MAP_MAX``)."""
    return _oauth_lock_map_max_entries()


def _get_token_lock(cache_key: str) -> asyncio.Lock:
    """
    Return the lock for ``cache_key``, LRU-touching on reuse.

    When the map exceeds :func:`_oauth_lock_map_max_entries`, the least-recently-used
    entry is evicted. A tiny risk of duplicate concurrent OAuth for that key until Redis
    is populated is acceptable at extreme multitenancy scale.
    """
    max_entries = _oauth_lock_map_max_entries()
    if cache_key in _token_fetch_locks:
        _token_fetch_locks.move_to_end(cache_key)
        return _token_fetch_locks[cache_key]
    while len(_token_fetch_locks) >= max_entries:
        evicted, _ = _token_fetch_locks.popitem(last=False)
        logger.debug(
            "[MindBot] oauth_lock_map_evicted oldest_key_prefix=%s remaining=%s max=%s",
            evicted[:56] if len(evicted) > 56 else evicted,
            len(_token_fetch_locks),
            max_entries,
        )
    lock = asyncio.Lock()
    _token_fetch_locks[cache_key] = lock
    return lock


def _oauth_credential_cache_suffix(app_key: str, app_secret: str) -> str:
    raw = f"{app_key.strip()}|{app_secret.strip()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def _token_cache_key(organization_id: int, app_key: str, app_secret: str) -> str:
    return (
        f"mindbot:dt_oauth:{organization_id}:"
        f"{_oauth_credential_cache_suffix(app_key, app_secret)}"
    )


def _parse_access_token(data: dict[str, Any]) -> str:
    """Extract token from DingTalk JSON (several documented shapes)."""
    for nested_key in ("data", "result"):
        inner = data.get(nested_key)
        if isinstance(inner, dict):
            tok = inner.get("accessToken") or inner.get("access_token")
            if isinstance(tok, str) and tok.strip():
                return tok.strip()
    tok = data.get("accessToken") or data.get("access_token")
    if isinstance(tok, str) and tok.strip():
        return tok.strip()
    return ""


def _oauth_error_snippet(data: dict[str, Any]) -> str:
    """Build a short operator-facing line from a failed OAuth JSON body."""
    parts: list[str] = []
    ec = data.get("errcode")
    if ec is not None and ec != 0:
        parts.append(f"errcode={ec}")
    code = data.get("code")
    if isinstance(code, str) and code.strip() and code.lower() not in ("0", "ok", "success"):
        parts.append(code.strip()[:160])
    msg = data.get("errmsg") or data.get("message") or data.get("msg")
    if isinstance(msg, str) and msg.strip():
        parts.append(msg.strip()[:400])
    if not parts and data.get("success") is False:
        parts.append("success=false")
    if not parts:
        return ""
    return " — ".join(parts)


def _http_oauth_error_detail(status: int, body_txt: str) -> str:
    """Prefer parsed DingTalk JSON on non-2xx (e.g. HTTP 400 + invalidClientIdOrSecret)."""
    try:
        data = json.loads(body_txt)
    except json.JSONDecodeError:
        return f"HTTP {status}: {_sanitize_oauth_snippet(body_txt)}"
    if not isinstance(data, dict):
        return f"HTTP {status}: {_sanitize_oauth_snippet(body_txt)}"
    snippet = _oauth_error_snippet(data)
    if snippet:
        return f"HTTP {status}: {snippet}"
    return f"HTTP {status}: {_sanitize_oauth_snippet(body_txt)}"


async def get_access_token_with_error(
    organization_id: int,
    app_key: str,
    app_secret: str,
) -> tuple[Optional[str], str]:
    """
    POST ``/v1.0/oauth2/accessToken`` with appKey / appSecret.

    Returns ``(token, "")`` on success. On failure returns ``(None, detail)`` where
    ``detail`` is suitable for admin UI (DingTalk message or HTTP snippet).

    https://open.dingtalk.com/document/orgapp-server/obtain-the-access-token-of-an-internal-app
    """
    if not (app_key or "").strip():
        return None, "app key (Client ID) is empty"
    if not (app_secret or "").strip():
        return (
            None,
            "app secret is empty — enter and save DingTalk Client Secret with the same app as Client ID",
        )

    key = _token_cache_key(organization_id, app_key, app_secret)
    cached = await redis_get(key)
    if cached:
        return cached, ""

    lock = _get_token_lock(key)
    async with lock:
        cached = await redis_get(key)
        if cached:
            return cached, ""

        payload = {"appKey": app_key.strip(), "appSecret": app_secret.strip()}
        timeout = aiohttp.ClientTimeout(total=30)
        try:
            session = get_dingtalk_api_session()
            async with session.post(
                f"{DING_API_BASE}{PATH_OAUTH_ACCESS_TOKEN}",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            ) as resp:
                body_txt = await resp.text()
                if resp.status != 200:
                    logger.warning(
                        "[MindBot] DingTalk accessToken failed: %s %s",
                        resp.status,
                        _sanitize_oauth_snippet(body_txt),
                    )
                    return None, _http_oauth_error_detail(resp.status, body_txt)
                try:
                    data = json.loads(body_txt)
                except json.JSONDecodeError:
                    logger.warning("[MindBot] DingTalk accessToken invalid JSON")
                    return None, "invalid JSON from DingTalk OAuth"
                if not isinstance(data, dict):
                    return None, "unexpected OAuth response type"
                token = _parse_access_token(data)
                if token:
                    await redis_set_ttl(key, token, TOKEN_TTL_SECONDS)
                    return token, ""
                err = _oauth_error_snippet(data)
                if not err:
                    err = f"no access_token in response ({_sanitize_oauth_snippet(body_txt)})"
                logger.warning("[MindBot] DingTalk accessToken missing token: %s", err)
                return None, err
        except Exception as exc:
            logger.exception("[MindBot] DingTalk accessToken request error: %s", exc)
            return None, "request error — check server logs for details"


async def get_access_token(
    organization_id: int,
    app_key: str,
    app_secret: str,
) -> Optional[str]:
    """Same as :func:`get_access_token_with_error` but returns only the token or ``None``."""
    token, _ = await get_access_token_with_error(organization_id, app_key, app_secret)
    return token


async def invalidate_access_token_cache(
    organization_id: int,
    app_key: str,
    app_secret: str,
) -> None:
    """Delete cached OAuth token so the next :func:`get_access_token` fetches a new one."""
    if not is_redis_available():
        return
    if not (app_key or "").strip() or not (app_secret or "").strip():
        return
    cache_key = _token_cache_key(organization_id, app_key, app_secret)
    await redis_delete(cache_key)
