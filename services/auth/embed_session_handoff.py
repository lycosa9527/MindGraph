"""
One-time Redis handoff codes for mgat_ → browser session bootstrap.

Used by Office Word add-in (and similar embeds): the shell POSTs with Bearer
mgat_, then navigates the WebView to GET complete on the API host so httpOnly
cookies are set on the SPA origin.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import secrets
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from services.redis import keys as redis_keys
from services.redis.redis_async_ops import AsyncRedisOps
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

HANDOFF_TTL_SECONDS = redis_keys.TTL_EMBED_SESSION_HANDOFF
_ALLOWED_PATH_PREFIXES = (
    "/mindgraph",
    "/mindmate",
    "/canvas",
    "/showcase",
)


def _handoff_key(code: str) -> str:
    return redis_keys.EMBED_SESSION_HANDOFF.format(code=code)


async def create_embed_handoff(user_id: int) -> Optional[str]:
    """Store a one-time handoff code for ``user_id``. Returns code or None."""
    code = secrets.token_urlsafe(32)
    try:
        ok = await AsyncRedisOps.set_with_ttl(
            _handoff_key(code),
            str(int(user_id)),
            HANDOFF_TTL_SECONDS,
        )
    except REDIS_ERRORS:
        logger.warning("[EmbedHandoff] Redis unavailable while creating code", exc_info=True)
        return None
    if not ok:
        return None
    return code


async def consume_embed_handoff(code: str) -> Optional[int]:
    """Consume handoff code once. Returns user_id or None."""
    cleaned = (code or "").strip()
    if not cleaned or len(cleaned) > 128:
        return None
    try:
        raw = await AsyncRedisOps.get_and_delete(_handoff_key(cleaned))
    except REDIS_ERRORS:
        logger.warning("[EmbedHandoff] Redis unavailable while consuming code", exc_info=True)
        return None
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def sanitize_embed_next_path(next_path: Optional[str]) -> str:
    """Allow only same-site absolute paths (no scheme/host open redirects)."""
    raw = (next_path or "").strip() or "/mindgraph"
    if not raw.startswith("/") or raw.startswith("//"):
        return "/mindgraph"
    if "\\" in raw or "://" in raw:
        return "/mindgraph"
    path_only = raw.split("?", 1)[0].split("#", 1)[0]
    if path_only == "/":
        return "/"
    for prefix in _ALLOWED_PATH_PREFIXES:
        if path_only == prefix or path_only.startswith(f"{prefix}/"):
            return path_only
    return "/mindgraph"


def append_embed_query(next_path: str, embed_client: str = "word-addin") -> str:
    """Ensure ``embed=<client>`` is present on the redirect path."""
    parts = urlsplit(next_path)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["embed"] = embed_client
    path = parts.path or "/mindgraph"
    return urlunsplit(("", "", path, urlencode(query), ""))
