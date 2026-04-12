"""OAuth access token for enterprise internal apps (cached in Redis)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, Optional

import aiohttp

from services.mindbot.platforms.dingtalk.constants import DING_API_BASE, PATH_OAUTH_ACCESS_TOKEN, TOKEN_TTL_SECONDS
from services.redis.redis_client import RedisOperations, is_redis_available

logger = logging.getLogger(__name__)


def _oauth_credential_cache_suffix(app_key: str, app_secret: str) -> str:
    raw = f"{app_key.strip()}|{app_secret.strip()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _token_cache_key(organization_id: int, app_key: str, app_secret: str) -> str:
    return (
        f"mindbot:dt_oauth:{organization_id}:"
        f"{_oauth_credential_cache_suffix(app_key, app_secret)}"
    )


def _redis_token_get(key: str) -> Optional[str]:
    if not is_redis_available():
        return None
    return RedisOperations.get(key)


def _redis_token_set(key: str, value: str, ttl: int) -> bool:
    if not is_redis_available():
        return False
    return RedisOperations.set_with_ttl(key, value, ttl)


async def _redis_token_get_async(key: str) -> Optional[str]:
    return await asyncio.to_thread(_redis_token_get, key)


async def _redis_token_set_async(key: str, value: str, ttl: int) -> bool:
    return await asyncio.to_thread(_redis_token_set, key, value, ttl)


def _parse_access_token(data: dict[str, Any]) -> str:
    inner = data.get("data")
    if isinstance(inner, dict):
        tok = inner.get("accessToken") or inner.get("access_token")
        if isinstance(tok, str) and tok.strip():
            return tok.strip()
    tok = data.get("accessToken") or data.get("access_token")
    if isinstance(tok, str) and tok.strip():
        return tok.strip()
    return ""


async def get_access_token(
    organization_id: int,
    app_key: str,
    app_secret: str,
) -> Optional[str]:
    """
    POST ``/v1.0/oauth2/accessToken`` with appKey / appSecret.

    https://open.dingtalk.com/document/orgapp-server/obtain-the-access-token-of-an-internal-app
    """
    key = _token_cache_key(organization_id, app_key, app_secret)
    cached = await _redis_token_get_async(key)
    if cached:
        return cached

    payload = {"appKey": app_key.strip(), "appSecret": app_secret.strip()}
    timeout = aiohttp.ClientTimeout(total=30)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{DING_API_BASE}{PATH_OAUTH_ACCESS_TOKEN}",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                body_txt = await resp.text()
                if resp.status != 200:
                    logger.warning(
                        "[MindBot] DingTalk accessToken failed: %s %s",
                        resp.status,
                        body_txt[:500],
                    )
                    return None
                try:
                    data = json.loads(body_txt)
                except json.JSONDecodeError:
                    logger.warning("[MindBot] DingTalk accessToken invalid JSON")
                    return None
                token = _parse_access_token(data)
                if not token:
                    logger.warning("[MindBot] DingTalk accessToken empty in response")
                    return None
                await _redis_token_set_async(key, token, TOKEN_TTL_SECONDS)
                return token
    except Exception as exc:
        logger.exception("[MindBot] DingTalk accessToken request error: %s", exc)
        return None
