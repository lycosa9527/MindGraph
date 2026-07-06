"""Shared HTTP helpers for WeCom webhook APIs (99110)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from services.utils.error_types import HTTP_CLIENT_ERRORS

logger = logging.getLogger(__name__)

WECOM_HTTP_TIMEOUT_SECONDS = 10.0


async def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST JSON body to a WeCom webhook endpoint."""
    async with httpx.AsyncClient(timeout=WECOM_HTTP_TIMEOUT_SECONDS) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("WeCom webhook response is not a JSON object")
        return body


def parse_wecom_response(body: dict[str, Any]) -> tuple[bool, int | None, str | None]:
    """Parse standard WeCom API JSON (`errcode` / `errmsg`)."""
    errcode_raw = body.get("errcode")
    errmsg_raw = body.get("errmsg")
    errmsg = str(errmsg_raw) if errmsg_raw is not None else None
    if errcode_raw is None:
        return False, None, errmsg or "missing errcode"
    try:
        errcode = int(errcode_raw)
    except (TypeError, ValueError):
        return False, None, errmsg or "invalid errcode"
    return errcode == 0, errcode, errmsg


async def post_json_safe(
    url: str,
    payload: dict[str, Any],
    *,
    channel: str,
    profile_id: str,
) -> tuple[dict[str, Any] | None, BaseException | None]:
    """POST JSON and capture transport errors without raising."""
    try:
        return await post_json(url, payload), None
    except httpx.HTTPError as exc:
        logger.warning("[WeCom] %s HTTP error profile=%s: %s", channel, profile_id, exc)
        return None, exc
    except HTTP_CLIENT_ERRORS as exc:
        logger.warning("[WeCom] %s failed profile=%s: %s", channel, profile_id, exc)
        return None, exc
