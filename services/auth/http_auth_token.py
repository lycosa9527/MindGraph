"""
Extract and decode JWT access tokens from HTTP and WebSocket scopes.

Extraction lives in ``bearer_token`` (cycle-safe leaf). This module adds JWT
decode helpers that need ``utils.auth`` secrets/config.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional

from fastapi import Request
from jose import JWTError, jwt

from services.auth.bearer_token import (
    extract_bearer_token,
    extract_bearer_token_from_websocket,
    extract_session_token,
    has_authorization_mgat_bearer,
    query_token_looks_like_session_credential,
)
from utils.auth.config import JWT_ALGORITHM
from utils.auth.connection_types import HttpOrWebSocket
from utils.auth.jwt_secret import get_jwt_secret

# Re-export extraction helpers for existing importers.
__all__ = [
    "extract_bearer_token",
    "extract_bearer_token_from_websocket",
    "extract_session_token",
    "has_authorization_mgat_bearer",
    "query_token_looks_like_session_credential",
    "try_decode_access_token_payload",
    "try_decode_access_token_payload_from_connection",
]


def try_decode_access_token_payload(request: Request) -> Optional[dict]:
    """Decode JWT access payload from HTTP request, or None for mgat_ / invalid / missing."""
    return try_decode_access_token_payload_from_connection(request)


def try_decode_access_token_payload_from_connection(connection: HttpOrWebSocket) -> Optional[dict]:
    """Decode JWT access payload from HTTP or WebSocket, or None for mgat_ / invalid / missing."""
    try:
        token = extract_session_token(connection)
        if not token or token.startswith("mgat_"):
            return None
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
    except (OSError, RuntimeError, ValueError, TypeError):
        return None
