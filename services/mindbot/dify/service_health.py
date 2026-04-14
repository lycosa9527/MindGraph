"""Probe Dify app API availability for MindBot admin UI (no secrets exposed)."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Tuple

import aiohttp

from services.mindbot.http_client import get_outbound_session

logger = logging.getLogger(__name__)


async def check_dify_app_api_reachable(
    base_url: str,
    api_key: str,
    *,
    timeout_s: float = 10.0,
) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Return (online, http_status, error_token).

    Dify's HTTP app API does not expose GET /v1/health; GET /v1/parameters
    validates the Bearer app key and returns 200 when the service is up.
    """
    key = (api_key or "").strip()
    if not key:
        return False, None, "api_key_not_configured"
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return False, None, "base_url_not_configured"
    url = f"{base}/parameters"
    headers = {"Authorization": f"Bearer {key}"}
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    try:
        session = get_outbound_session()
        async with session.get(url, headers=headers, timeout=timeout) as resp:
                status = resp.status
                if status == 200:
                    await resp.read()
                    return True, status, None
                body_preview = (await resp.text())[:200]
                err = f"http_{status}"
                if body_preview:
                    err = f"{err}: {body_preview}"
                return False, status, err
    except asyncio.TimeoutError:
        return False, None, "timeout"
    except aiohttp.ClientError as exc:
        logger.warning("Dify health probe client error: %s", exc)
        return False, None, str(exc)[:200]
