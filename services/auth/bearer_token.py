"""
Extract Bearer / cookie / shaped ``?token=`` credentials from HTTP and WebSocket.

Leaf module (no ``utils.auth`` imports) so auth package init cannot cycle through
JWT helpers when resolving tokens.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional, Union

from fastapi import Request, WebSocket

HttpOrWebSocket = Union[Request, WebSocket]


def query_token_looks_like_session_credential(raw: str) -> bool:
    """
    Return True if ``?token=`` may be an access or mgat_ token (not an opaque
    per-feature secret such as quick-registration channel tokens).
    """
    token = raw.strip()
    if not token:
        return False
    if token.startswith("mgat_"):
        return True
    return token.count(".") >= 2


def has_authorization_mgat_bearer(request: Request) -> bool:
    """True when the client sent ``Authorization: Bearer mgat_…``."""
    credentials = request.headers.get("Authorization", "")
    if not credentials.startswith("Bearer "):
        return False
    return credentials[7:].strip().startswith("mgat_")


def extract_bearer_token(request: Request) -> Optional[str]:
    """
    Session token: Authorization Bearer, then access_token cookie, then ``?token=``
    only if it plausibly matches a JWT (three segments) or ``mgat_``.
    """
    credentials = request.headers.get("Authorization", "")
    if credentials.startswith("Bearer "):
        token = credentials[7:].strip()
        if token:
            return token
    cookie_token = request.cookies.get("access_token")
    if cookie_token and cookie_token.strip():
        return cookie_token.strip()
    query_token = request.query_params.get("token")
    if not query_token or not query_token.strip():
        return None
    if query_token_looks_like_session_credential(query_token):
        return query_token.strip()
    return None


def extract_bearer_token_from_websocket(websocket: WebSocket) -> Optional[str]:
    """
    Session token for WebSocket: Bearer, cookie, then shaped ``?token=``.

    ``?token=`` is the browser fallback when custom headers are unavailable
    (Word add-in Voice dialog). Prefer cookies when the page is same-origin.
    """
    auth = websocket.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        bearer = auth[7:].strip()
        if bearer:
            return bearer
    from_cookie = (websocket.cookies.get("access_token") or "").strip()
    if from_cookie:
        return from_cookie
    query = (websocket.query_params.get("token") or "").strip()
    if not query:
        return None
    if query_token_looks_like_session_credential(query):
        return query
    return None


def extract_session_token(connection: HttpOrWebSocket) -> Optional[str]:
    """Session token from HTTP request or WebSocket."""
    if isinstance(connection, WebSocket):
        return extract_bearer_token_from_websocket(connection)
    return extract_bearer_token(connection)
