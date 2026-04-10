"""
Extract and decode JWT access tokens from HTTP requests (Bearer, query, cookie).

Shared by VPN/geo middleware and auth helpers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional

from fastapi import Request
from jose import JWTError, jwt

from utils.auth.config import JWT_ALGORITHM
from utils.auth.jwt_secret import get_jwt_secret


def extract_bearer_token(request: Request) -> Optional[str]:
    query_token = request.query_params.get("token")
    if query_token and query_token.strip():
        return query_token.strip()
    credentials = request.headers.get("Authorization", "")
    if credentials.startswith("Bearer "):
        token = credentials[7:].strip()
        if token:
            return token
    cookie_token = request.cookies.get("access_token")
    if cookie_token and cookie_token.strip():
        return cookie_token.strip()
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
