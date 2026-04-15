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

Both sessions are created lazily on the first request (must run inside a live
asyncio event loop) and closed during the FastAPI lifespan shutdown via
``close_mindbot_http_sessions()``.

Using a shared session means:
- TCP + TLS connections to api.dingtalk.com are reused across requests.
- DNS results are cached for the connector TTL window.
- No per-call TLS handshake overhead — critical for streaming card updates
  that call ``PUT /v1.0/card/streaming`` on every Dify batch.
"""

from __future__ import annotations

import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

_dingtalk_session: Optional[aiohttp.ClientSession] = None
_outbound_session: Optional[aiohttp.ClientSession] = None
_shutting_down: bool = False


def get_dingtalk_api_session() -> aiohttp.ClientSession:
    """
    Return the shared ``aiohttp.ClientSession`` for ``api.dingtalk.com``.

    Created lazily on first call (requires a running event loop).
    Callers must pass ``timeout`` per-request — **not** per-session.
    """
    global _dingtalk_session  # pylint: disable=global-statement
    if _shutting_down:
        raise RuntimeError("MindBot HTTP sessions have been closed (shutdown in progress)")
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


async def close_mindbot_http_sessions() -> None:
    """
    Gracefully close both shared sessions.

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
