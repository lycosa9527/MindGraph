"""Temporary public hosting for audio files so DashScope ASR can fetch them.

DashScope's async recording-file API only accepts publicly reachable URLs (no
upload, no base64). File Center audio lives on local disk, so we mint a random,
short-lived token mapped (in Redis) to the on-disk path and expose it via an
unauthenticated fetch route (``/api/knowledge-space/audio-fetch/{token}``).

Security properties:
- Token is a cryptographically random ``secrets.token_urlsafe`` value (unguessable).
- Token → path mapping auto-expires (Redis TTL) and is revoked after use.
- The client never supplies a path, so the fetch route cannot be used for
  path traversal; it serves only files we explicitly registered.

Requires a publicly reachable ``EXTERNAL_HOST`` (or ``KNOWLEDGE_AUDIO_PUBLIC_BASE``)
so Alibaba Cloud can reach the server.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import secrets
from typing import Optional

from config.settings import config
from services.redis.redis_client import get_redis
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

_TOKEN_PREFIX = "kb:audio:fetch:"
# Token lifetime: long enough for DashScope to fetch + transcribe, then expires.
_DEFAULT_TTL_SEC = 3600
_FETCH_ROUTE = "/api/knowledge-space/audio-fetch/"


def publish_audio(file_path: str, ttl_sec: int = _DEFAULT_TTL_SEC) -> tuple[str, str]:
    """Register an audio file for temporary public fetch; return ``(token, url)``.

    Raises ``RuntimeError`` if Redis is unavailable so the caller can fail the
    source rather than submit an unreachable URL.
    """
    token = secrets.token_urlsafe(32)
    client = get_redis()
    if client is None:
        raise RuntimeError("Redis unavailable; cannot host audio for transcription")
    try:
        client.setex(f"{_TOKEN_PREFIX}{token}", ttl_sec, str(file_path))
    except REDIS_ERRORS as exc:
        raise RuntimeError(f"Failed to register audio for transcription hosting: {exc}") from exc

    url = f"{config.KNOWLEDGE_AUDIO_PUBLIC_BASE}{_FETCH_ROUTE}{token}"
    logger.info("[AudioHosting] Published audio token (ttl=%ds): %s", ttl_sec, url)
    return token, url


def resolve_audio_path(token: str) -> Optional[str]:
    """Return the on-disk path registered for a fetch token, or ``None``."""
    if not token:
        return None
    client = get_redis()
    if client is None:
        return None
    try:
        value = client.get(f"{_TOKEN_PREFIX}{token}")
    except REDIS_ERRORS as exc:
        logger.warning("[AudioHosting] Failed to resolve audio token: %s", exc)
        return None
    if value is None:
        return None
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def revoke_audio(token: str) -> None:
    """Best-effort delete of a fetch token after transcription completes."""
    if not token:
        return
    client = get_redis()
    if client is None:
        return
    try:
        client.delete(f"{_TOKEN_PREFIX}{token}")
    except REDIS_ERRORS as exc:
        logger.debug("[AudioHosting] Failed to revoke audio token: %s", exc)
