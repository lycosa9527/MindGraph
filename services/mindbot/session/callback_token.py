"""Opaque public tokens for per-organization DingTalk callback URLs."""

from __future__ import annotations

import secrets


def new_public_callback_token() -> str:
    """
    Return a URL-safe secret for /dingtalk/callback/t/{token}.

    Uses ~128 bits of entropy (22 chars from token_urlsafe(16)). Shorter fixed-length
    tokens (e.g. 6 alphanumeric) are too easy to guess for an unauthenticated URL.
    """
    return secrets.token_urlsafe(16)
