"""
Extract and decode JWT access tokens from HTTP and WebSocket scopes (Bearer,
cookie, then query ?token= only when it plausibly identifies a session).

Shared by VPN/geo middleware, auth context middleware, and WebSocket auth.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional

from fastapi import Request, WebSocket
from jose import JWTError, jwt

from utils.auth.config import JWT_ALGORITHM
from utils.auth.jwt_secret import get_jwt_secret


def _query_token_looks_like_session_credential(s: str) -> bool:
    """
    Return True if ?token= may be an access or mgat_ token (not an opaque
    per-feature secret such as quick-registration channel tokens).
    """
    t = s.strip()
    if not t:
        return False
    if t.startswith("mgat_"):
        return True
    return t.count(".") >= 2


def extract_bearer_token(request: Request) -> Optional[str]:
    """
    Session token: Authorization: Bearer, then access_token cookie, then ?token=
    only if it plausibly matches a JWT (three segments) or mgat_.
    Opaque ?token= (e.g. quick-register channel keys) is ignored for auth
    so middleware does not try to parse it as a JWT.
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
    if _query_token_looks_like_session_credential(query_token):
        return query_token.strip()
    return None


def extract_bearer_token_from_websocket(websocket: WebSocket) -> Optional[str]:
    """
    Session token for WebSocket: same policy as ``extract_bearer_token`` (Bearer
    header, then cookie, then ?token= only if JWT- or mgat_-shaped). Ignores
    opaque query ?token= so channel secrets are not sent to the JWT decoder.
    """
    auth = websocket.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        bearer = auth[7:].strip()
        if bearer:
            return bearer
    from_cookie = (websocket.cookies.get("access_token") or "").strip()
    if from_cookie:
        return from_cookie
    q = (websocket.query_params.get("token") or "").strip()
    if not q:
        return None
    if _query_token_looks_like_session_credential(q):
        return q
    return None


def try_decode_access_token_payload(request: Request) -> Optional[dict]:
    """Decode JWT access payload, or None for mgat_ / invalid / missing."""
    try:
        token = extract_bearer_token(request)
        if not token or token.startswith("mgat_"):
            return None
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
    except (OSError, RuntimeError, ValueError, TypeError):
        return None
