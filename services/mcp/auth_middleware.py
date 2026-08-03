"""
ASGI auth wrapper for MindGraph Streamable HTTP MCP.

Requires validated Bearer mgat_ + X-MG-Account before the MCP protocol runs.
Applies a per-user rate limit after successful auth.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from services.redis.rate_limiting.redis_rate_limiter import RedisRateLimiter
from utils.auth.mg_client import MG_CLIENT_HEADER
from utils.auth.user_tokens import validate_user_token

_AUTH_METHODS = frozenset({"GET", "POST", "DELETE"})
_MCP_RATE_MAX = 100
_MCP_RATE_WINDOW = 60
_DEFAULT_MG_CLIENT = "mcp"


async def _check_mcp_rate_limit(user_id: int) -> None:
    """Raise HTTP 429 when the per-user MCP rate limit is exceeded."""
    rate_limiter = RedisRateLimiter()
    is_allowed, _count, error_msg = await rate_limiter.check_and_record(
        category="api_mcp_http",
        identifier=f"user:{user_id}",
        max_attempts=_MCP_RATE_MAX,
        window_seconds=_MCP_RATE_WINDOW,
    )
    if not is_allowed:
        raise HTTPException(status_code=429, detail=f"Too many requests. {error_msg}")


def _header_bytes(scope: Scope, name: str) -> bytes:
    """Return the first matching header value (name is lowercase ASCII)."""
    target = name.lower().encode("latin-1")
    for key, value in scope.get("headers") or []:
        if key.lower() == target:
            return value
    return b""


def _header_str(scope: Scope, name: str) -> str:
    """Decode a request header as stripped text."""
    return _header_bytes(scope, name).decode("latin-1", errors="replace").strip()


def _ensure_mg_client_header(scope: Scope) -> Scope:
    """Default X-MG-Client to mcp when absent; return scope (possibly copied)."""
    existing = _header_str(scope, MG_CLIENT_HEADER)
    if existing:
        return scope

    headers = list(scope.get("headers") or [])
    target = MG_CLIENT_HEADER.lower().encode("latin-1")
    headers.append((target, _DEFAULT_MG_CLIENT.encode("latin-1")))
    new_scope = dict(scope)
    new_scope["headers"] = headers
    return new_scope


async def _send_json_error(send: Send, status_code: int, detail: Any) -> None:
    """Send a small JSON error response matching FastAPI HTTPException shape."""
    body = json.dumps({"detail": detail}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("latin-1")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class McpMgatAuthMiddleware:
    """
    Require mgat_ API token auth for MCP Streamable HTTP methods.

    OPTIONS is passed through for CORS preflight. Successful auth applies the
    ``mcp_http`` rate limit before the inner MCP app runs.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = (scope.get("method") or "GET").upper()
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        if method not in _AUTH_METHODS:
            await _send_json_error(send, 405, "Method Not Allowed")
            return

        scope = _ensure_mg_client_header(scope)
        request = Request(scope, receive)
        auth = _header_str(scope, "authorization")
        account = _header_str(scope, "x-mg-account")

        if not auth.lower().startswith("bearer "):
            await _send_json_error(
                send,
                401,
                "Authorization header must be Bearer token (mgat_...)",
            )
            return

        token = auth[7:].strip()
        if not token.startswith("mgat_"):
            await _send_json_error(
                send,
                401,
                "Authorization header must be Bearer token (mgat_...)",
            )
            return

        try:
            user = await validate_user_token(token, account, request=request)
            await _check_mcp_rate_limit(int(user.id))
        except HTTPException as exc:
            await _send_json_error(send, exc.status_code, exc.detail)
            return

        request.state.auth_context_user = user
        await self.app(scope, receive, send)
