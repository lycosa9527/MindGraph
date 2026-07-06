"""WeCom corp app message/send with cached gettoken (docs 91039 + 90236)."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from services.integrations.wecom.config import WeComCorpConfig, load_wecom_corp_config
from services.integrations.wecom.profiles import WeComNotifyProfile
from services.integrations.wecom.types import WeComChannelResult, WeComMessage
from services.utils.error_types import HTTP_CLIENT_ERRORS

logger = logging.getLogger(__name__)

WECOM_API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"
WECOM_HTTP_TIMEOUT_SECONDS = 10.0
TOKEN_REFRESH_BUFFER_SECONDS = 120

_token_cache: dict[str, tuple[str, float]] = {}


async def _get_json(url: str, params: dict[str, str]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=WECOM_HTTP_TIMEOUT_SECONDS) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("WeCom API response is not a JSON object")
        return body


async def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=WECOM_HTTP_TIMEOUT_SECONDS) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("WeCom API response is not a JSON object")
        return body


def _parse_wecom_response(body: dict[str, Any]) -> tuple[bool, int | None, str | None]:
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


def clear_access_token_cache() -> None:
    """Clear cached tokens (for tests)."""
    _token_cache.clear()


async def get_access_token(corp: WeComCorpConfig) -> str:
    """Fetch and cache access_token via gettoken."""
    cache_key = f"{corp.corp_id}:{corp.agent_secret}"
    cached = _token_cache.get(cache_key)
    now = time.time()
    if cached is not None and cached[1] > now + TOKEN_REFRESH_BUFFER_SECONDS:
        return cached[0]

    url = f"{WECOM_API_BASE}/gettoken"
    params = {"corpid": corp.corp_id, "corpsecret": corp.agent_secret}
    body = await _get_json(url, params)
    ok, errcode, errmsg = _parse_wecom_response(body)
    if not ok:
        raise RuntimeError(f"WeCom gettoken failed: errcode={errcode} errmsg={errmsg}")

    token_raw = body.get("access_token")
    if not isinstance(token_raw, str) or not token_raw.strip():
        raise RuntimeError("WeCom gettoken returned empty access_token")

    expires_raw = body.get("expires_in", 7200)
    try:
        expires_in = int(expires_raw)
    except (TypeError, ValueError):
        expires_in = 7200

    token = token_raw.strip()
    _token_cache[cache_key] = (token, now + expires_in)
    return token


def format_touser(userids: tuple[str, ...]) -> str:
    """Join recipient userids with pipe separator (90236)."""
    return "|".join(userids)


async def send_app_message(
    profile: WeComNotifyProfile,
    message: WeComMessage,
    corp: WeComCorpConfig | None = None,
) -> WeComChannelResult:
    """Send text app message to configured notify_userids."""
    if not profile.app_message_enabled:
        return WeComChannelResult(
            channel="app_message",
            ok=False,
            skipped=True,
            skip_reason="notify_userids_not_configured",
        )

    corp_config = corp if corp is not None else load_wecom_corp_config()
    if not corp_config.is_complete:
        return WeComChannelResult(
            channel="app_message",
            ok=False,
            skipped=True,
            skip_reason="corp_app_not_configured",
        )

    touser = format_touser(profile.notify_userids)
    if not touser:
        return WeComChannelResult(
            channel="app_message",
            ok=False,
            skipped=True,
            skip_reason="empty_notify_userids",
        )

    try:
        access_token = await get_access_token(corp_config)
    except httpx.HTTPError as exc:
        logger.warning("[WeCom] gettoken HTTP error for profile %s: %s", profile.profile_id, exc)
        return WeComChannelResult(channel="app_message", ok=False, errmsg=str(exc))
    except HTTP_CLIENT_ERRORS as exc:
        logger.warning("[WeCom] gettoken failed for profile %s: %s", profile.profile_id, exc)
        return WeComChannelResult(channel="app_message", ok=False, errmsg=str(exc))
    except RuntimeError as exc:
        logger.warning("[WeCom] gettoken failed for profile %s: %s", profile.profile_id, exc)
        return WeComChannelResult(channel="app_message", ok=False, errmsg=str(exc))

    payload = {
        "touser": touser,
        "msgtype": "text",
        "agentid": corp_config.agent_id,
        "text": {
            "content": message.render_plain_text(),
        },
        "enable_duplicate_check": 0,
    }
    url = f"{WECOM_API_BASE}/message/send"
    try:
        body = await _post_json(f"{url}?access_token={access_token}", payload)
    except httpx.HTTPError as exc:
        logger.warning("[WeCom] message/send HTTP error for profile %s: %s", profile.profile_id, exc)
        return WeComChannelResult(channel="app_message", ok=False, errmsg=str(exc))
    except HTTP_CLIENT_ERRORS as exc:
        logger.warning("[WeCom] message/send failed for profile %s: %s", profile.profile_id, exc)
        return WeComChannelResult(channel="app_message", ok=False, errmsg=str(exc))

    ok, errcode, errmsg = _parse_wecom_response(body)
    if not ok:
        logger.warning(
            "[WeCom] message/send errcode=%s errmsg=%s profile=%s",
            errcode,
            errmsg,
            profile.profile_id,
        )
    return WeComChannelResult(channel="app_message", ok=ok, errcode=errcode, errmsg=errmsg)
