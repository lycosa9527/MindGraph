"""Shared aiohttp sessions for all MindBot HTTP I/O.

Two long-lived sessions are maintained for the lifetime of the application:

``dingtalk_api``
    All calls to ``https://api.dingtalk.com`` — card creation/streaming,
    OAuth token, robot send, message-file download-URL, robot query/recall.
    Tuned for a persistent, high-concurrency pool to api.dingtalk.com.

``outbound``
    Session webhook POSTs (arbitrary DingTalk CDN URLs), media/file byte
    downloads, legacy ``oapi.dingtalk.com`` uploads, and Dify health probes.
    Uses a looser per-host limit since targets vary per message.

In addition, a small bounded LRU of **pinned-IP** sessions is maintained for
session-webhook POSTs that must connect to a pre-resolved IP (DNS rebinding
protection — see ``services.mindbot.session.webhook_url``).  Without this
cache every streaming chunk would build a new TLS connection because
``aiohttp`` does not support per-request resolvers and the SSRF guard requires
pinning the resolved IP at validation time.  The cache is keyed by
``(host, pinned_ip)`` so DNS rotations naturally produce a fresh session.

All sessions are created lazily on first request (must run inside a live
asyncio event loop) and closed during the FastAPI lifespan shutdown via
``close_mindbot_http_sessions()``.

Using shared sessions means:
- TCP + TLS connections are reused across requests.
- DNS results are cached for the connector TTL window.
- No per-call TLS handshake overhead — critical for streaming card updates
  that call ``PUT /v1.0/card/streaming`` on every Dify batch.
"""

from __future__ import annotations

import collections
import logging
import ssl
from typing import Optional

import aiohttp
import aiohttp.resolver

from utils.env_helpers import env_int

logger = logging.getLogger(__name__)

_dingtalk_session: Optional[aiohttp.ClientSession] = None
_outbound_session: Optional[aiohttp.ClientSession] = None
_shutting_down: bool = False

_PINNED_DEFAULT_MAX = 64

_pinned_sessions: "collections.OrderedDict[tuple[str, str], aiohttp.ClientSession]" = collections.OrderedDict()


def _pinned_max() -> int:
    return max(8, env_int("MINDBOT_PINNED_SESSION_MAX", _PINNED_DEFAULT_MAX))


class _PinnedIPResolver(aiohttp.resolver.AbstractResolver):
    """aiohttp resolver that always returns a pre-resolved IP for any host.

    Bound to a single ``(host, pinned_ip)`` cache entry so DNS rebinding cannot
    redirect the connection to a private address after the SSRF check passed.
    TLS SNI / certificate verification still use the original hostname because
    ``aiohttp`` derives ``server_hostname`` from the URL, not the resolved IP.
    """

    def __init__(self, pinned_ip: str) -> None:
        self._pinned_ip = pinned_ip

    async def resolve(self, host: str, port: int = 0, family: int = 0) -> list[dict]:
        return [
            {
                "hostname": host,
                "host": self._pinned_ip,
                "port": port,
                "family": family,
                "proto": 0,
                "flags": 0,
            }
        ]

    async def close(self) -> None:
        return None


def get_dingtalk_api_session() -> aiohttp.ClientSession:
    """
    Return the shared ``aiohttp.ClientSession`` for ``api.dingtalk.com``.

    Created lazily on first call (requires a running event loop).
    Callers must pass ``timeout`` per-request — **not** per-session.
    """
    global _dingtalk_session  # pylint: disable=global-statement
    if _shutting_down:
        raise RuntimeError("MindBot HTTP sessions have been closed (shutdown in progress)")
    # No asyncio.Lock needed: ClientSession() construction has no await, so the
    # check-and-assign block runs atomically within a single event-loop tick.
    # This function must NOT be called from threads outside the event loop.
    if _dingtalk_session is None or _dingtalk_session.closed:
        connector = aiohttp.TCPConnector(
            limit=200,
            limit_per_host=60,
            ttl_dns_cache=300,
            keepalive_timeout=30,
            enable_cleanup_closed=True,
        )
        _dingtalk_session = aiohttp.ClientSession(connector=connector)
        logger.debug("[MindBot] dingtalk_api_session created")
    return _dingtalk_session


def get_outbound_session() -> aiohttp.ClientSession:
    """
    Return the shared ``aiohttp.ClientSession`` for outbound / webhook calls.

    Used for session-webhook POSTs, media downloads, oapi uploads, and Dify
    health probes — targets vary per message so ``limit_per_host`` is wider.
    Created lazily on first call (requires a running event loop).
    """
    global _outbound_session  # pylint: disable=global-statement
    if _shutting_down:
        raise RuntimeError("MindBot HTTP sessions have been closed (shutdown in progress)")
    # No asyncio.Lock needed: same rationale as get_dingtalk_api_session above.
    if _outbound_session is None or _outbound_session.closed:
        connector = aiohttp.TCPConnector(
            limit=300,
            limit_per_host=30,
            ttl_dns_cache=60,
            keepalive_timeout=20,
            enable_cleanup_closed=True,
        )
        _outbound_session = aiohttp.ClientSession(connector=connector)
        logger.debug("[MindBot] outbound_session created")
    return _outbound_session


async def get_pinned_outbound_session(
    host: str,
    pinned_ip: str,
) -> aiohttp.ClientSession:
    """
    Return a cached ``aiohttp.ClientSession`` pinned to ``(host, pinned_ip)``.

    Reuses TCP + TLS connections across streaming chunks bound to the same
    DingTalk session-webhook host.  Bounded LRU eviction (default 64 entries)
    closes the oldest session when capacity is exceeded so memory cannot grow
    unbounded across distinct webhooks.

    The cache key includes both host and pinned IP — when DNS rotates and a
    later validation produces a different IP, callers automatically get a
    fresh session and the stale entry is closed on next overflow.

    Async because eviction may need to ``await session.close()`` cleanly; the
    function still completes in O(1) on cache hit (no awaits on the hot path).
    """
    if _shutting_down:
        raise RuntimeError("MindBot HTTP sessions have been closed (shutdown in progress)")
    key = (host, pinned_ip)
    cached = _pinned_sessions.get(key)
    if cached is not None and not cached.closed:
        _pinned_sessions.move_to_end(key)
        return cached
    if cached is not None and cached.closed:
        _pinned_sessions.pop(key, None)

    max_entries = _pinned_max()
    while len(_pinned_sessions) >= max_entries:
        evicted_key, evicted = _pinned_sessions.popitem(last=False)
        if evicted is not None and not evicted.closed:
            try:
                await evicted.close()
            except Exception as exc:  # pylint: disable=broad-except
                logger.debug(
                    "[MindBot] pinned_session_evict_close_error host=%s err=%s",
                    evicted_key[0],
                    exc,
                )

    resolver = _PinnedIPResolver(pinned_ip)
    ssl_ctx = ssl.create_default_context()
    connector = aiohttp.TCPConnector(
        resolver=resolver,
        ssl=ssl_ctx,
        limit=20,
        limit_per_host=10,
        keepalive_timeout=30,
        enable_cleanup_closed=True,
    )
    session = aiohttp.ClientSession(connector=connector)
    _pinned_sessions[key] = session
    logger.debug(
        "[MindBot] pinned_session_created host=%s pinned_ip_tail=%s cache_size=%s",
        host,
        pinned_ip[-8:] if len(pinned_ip) > 8 else pinned_ip,
        len(_pinned_sessions),
    )
    return session


def pinned_session_cache_size() -> int:
    """Current number of cached pinned-IP sessions (for diagnostics)."""
    return len(_pinned_sessions)


async def close_mindbot_http_sessions() -> None:
    """
    Gracefully close all shared sessions, including pinned-IP cache entries.

    Call once from the FastAPI lifespan ``finally`` block.  After this returns
    no further HTTP calls should be made via these sessions.
    """
    global _dingtalk_session, _outbound_session, _shutting_down  # pylint: disable=global-statement
    _shutting_down = True
    for name, session in [
        ("dingtalk_api", _dingtalk_session),
        ("outbound", _outbound_session),
    ]:
        if session and not session.closed:
            try:
                await session.close()
                logger.info("[MindBot] http_session_closed session=%s", name)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "[MindBot] http_session_close_error session=%s err=%s",
                    name,
                    exc,
                )
    _dingtalk_session = None
    _outbound_session = None

    pinned_keys = list(_pinned_sessions.keys())
    for key in pinned_keys:
        sess = _pinned_sessions.pop(key, None)
        if sess is not None and not sess.closed:
            try:
                await sess.close()
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "[MindBot] pinned_session_close_error host=%s err=%s",
                    key[0],
                    exc,
                )
    if pinned_keys:
        logger.info(
            "[MindBot] pinned_sessions_closed count=%s",
            len(pinned_keys),
        )
