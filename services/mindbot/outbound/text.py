"""DingTalk outbound helpers for MindBot (OpenAPI send, session webhook POST)."""

from __future__ import annotations

import json
import logging
import re
import ssl
from typing import Any, Optional

import aiohttp
import aiohttp.resolver

from services.mindbot.infra.http_client import get_outbound_session
from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.telemetry.pipeline_log import session_webhook_host
from utils.env_helpers import env_bool

from services.mindbot.platforms.dingtalk import (
    build_session_webhook_payload,
    openapi_robot_msg_param_for_answer,
    openapi_robot_msg_param_stream_chunk,
)
from services.mindbot.platforms.dingtalk.api.constants import (
    PATH_ROBOT_GROUP_MESSAGES_SEND,
    PATH_ROBOT_OTO_MESSAGES_BATCH_SEND,
)
from services.mindbot.platforms.dingtalk.api.http import post_v1_json
from services.mindbot.platforms.dingtalk.auth.oauth import (
    get_access_token_with_error,
    invalidate_access_token_cache,
)

logger = logging.getLogger(__name__)

_SENSITIVE_PATTERN = re.compile(
    r'("(?:accessToken|access_token|token|secret|password)")\s*:\s*"[^"]{4,}"',
    re.IGNORECASE,
)


def _sanitize_webhook_snippet(body_txt: str, max_len: int = 400) -> str:
    """Return a truncated, token-redacted snippet safe for WARNING logs."""
    snippet = body_txt[:max_len]
    return _SENSITIVE_PATTERN.sub(r'\1: "***"', snippet)


class _PinnedIPResolver(aiohttp.resolver.AbstractResolver):
    """aiohttp resolver that returns a pre-resolved IP, bypassing DNS at request time.

    This prevents DNS rebinding attacks: the hostname was resolved and validated
    at callback time; subsequent requests use the pinned IP so a rogue DNS TTL-0
    response cannot redirect the connection to a private address.

    TLS SNI and certificate verification still use the original hostname because
    aiohttp derives ``server_hostname`` from the URL's host component, not the
    resolved IP.
    """

    def __init__(self, pinned_ip: str) -> None:
        self._pinned_ip = pinned_ip

    async def resolve(self, host: str, port: int = 0, family: int = 0) -> list[dict]:
        return [
            {
                "hostname": host,
                "host": self._pinned_ip,
                "port": port,
                "family": family,
                "proto": 0,
                "flags": 0,
            }
        ]

    async def close(self) -> None:
        pass


def is_group_conversation(body: dict[str, Any]) -> bool:
    ct = body.get("conversationType") or body.get("conversation_type")
    if ct is None:
        return False
    s = str(ct).strip().lower()
    return s in ("2", "group")


async def reply_via_openapi(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    answer: str,
    *,
    stream_chunk: bool = False,
    pipeline_ctx: str = "",
) -> tuple[bool, bool]:
    """
    Try OpenAPI send. Returns (success, token_failed).

    ``token_failed`` is True only when token acquisition failed (vs send failure).

    On HTTP 401, the cached token is invalidated and one retry is attempted with a
    fresh token so expired tokens do not require manual intervention.
    """
    if not env_bool("MINDBOT_OPENAPI_ENABLED", True):
        return False, False
    if not env_bool("MINDBOT_FALLBACK_OPENAPI_SEND", True):
        return False, False
    app_key = (cfg.dingtalk_client_id or "").strip()
    if not app_key:
        return False, False
    app_secret = cfg.dingtalk_app_secret.strip()
    token, _err = await get_access_token_with_error(
        cfg.organization_id,
        app_key,
        app_secret,
    )
    if not token:
        logger.warning("[MindBot] OpenAPI fallback: no access token")
        return False, True
    robot_code = cfg.dingtalk_robot_code.strip()
    sender = body.get("senderStaffId") or body.get("sender_staff_id")
    sender_s = sender.strip() if isinstance(sender, str) else ""
    conv_id = body.get("conversationId") or body.get("conversation_id")
    conv_s = conv_id.strip() if isinstance(conv_id, str) else ""
    if stream_chunk:
        msg_key, msg_param = openapi_robot_msg_param_stream_chunk(answer)
    else:
        msg_key, msg_param = openapi_robot_msg_param_for_answer(answer)
    is_group = is_group_conversation(body)
    if is_group and not conv_s:
        logger.warning("[MindBot] OpenAPI group fallback: missing conversationId")
        return False, False
    if not is_group and not sender_s:
        logger.warning("[MindBot] OpenAPI private fallback: missing senderStaffId")
        return False, False

    effective_token = token
    for attempt in range(2):
        if is_group:
            payload = {
                "msgKey": msg_key,
                "msgParam": json.dumps(msg_param, ensure_ascii=False),
                "openConversationId": conv_s,
                "robotCode": robot_code,
            }
            path = PATH_ROBOT_GROUP_MESSAGES_SEND
        else:
            payload = {
                "robotCode": robot_code,
                "userIds": [sender_s],
                "msgKey": msg_key,
                "msgParam": json.dumps(msg_param, ensure_ascii=False),
            }
            path = PATH_ROBOT_OTO_MESSAGES_BATCH_SEND
        status, res = await post_v1_json(path, effective_token, payload)
        if status == 200 and res is not None:
            log_fn = logger.debug if stream_chunk else logger.info
            log_fn(
                "[MindBot] outbound_openapi %s chat=%s chunk=%s answer_chars=%s",
                pipeline_ctx,
                "group" if is_group else "oto",
                stream_chunk,
                len(answer),
            )
            return True, False
        if status == 401 and attempt == 0:
            logger.info(
                "[MindBot] outbound_openapi_401_retry %s path=%s invalidating_token",
                pipeline_ctx,
                path,
            )
            await invalidate_access_token_cache(cfg.organization_id, app_key, app_secret)
            new_token, _err2 = await get_access_token_with_error(
                cfg.organization_id, app_key, app_secret
            )
            if new_token:
                effective_token = new_token
                continue
            logger.warning("[MindBot] outbound_openapi_401_retry %s token_refresh_failed", pipeline_ctx)
        break

    logger.warning(
        "[MindBot] outbound_openapi_failed %s chat=%s status=%s",
        pipeline_ctx,
        "group" if is_group else "oto",
        status,
    )
    return False, False


async def _do_post_session_webhook(
    session: aiohttp.ClientSession,
    url: str,
    payload_str: str,
    timeout: aiohttp.ClientTimeout,
    host: str,
    stream_chunk: bool,
    pipeline_ctx: str,
) -> bool:
    """Execute the actual webhook POST and handle response/errors."""
    try:
        async with session.post(
            url,
            data=payload_str,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=timeout,
            allow_redirects=False,
        ) as r:
            if not (200 <= r.status < 300):
                body_txt = await r.text()
                logger.warning(
                    "[MindBot] outbound_session_webhook_http %s host=%s status=%s body=%s",
                    pipeline_ctx,
                    host,
                    r.status,
                    _sanitize_webhook_snippet(body_txt),
                )
                return False
            await r.read()
    except Exception as exc:
        logger.exception(
            "[MindBot] outbound_session_webhook_error %s host=%s: %s",
            pipeline_ctx,
            host,
            exc,
        )
        return False
    payload_chars = len(payload_str)
    log_ok = logger.debug if stream_chunk else logger.info
    log_ok(
        "[MindBot] outbound_session_webhook_ok %s host=%s chunk=%s payload_chars=%s",
        pipeline_ctx,
        host,
        stream_chunk,
        payload_chars,
    )
    return True


async def post_session_webhook(
    session_webhook: str,
    answer: str,
    *,
    stream_chunk: bool = False,
    pipeline_ctx: str = "",
    pinned_ip: str = "",
) -> bool:
    """POST ``answer`` to the DingTalk session webhook.

    When ``pinned_ip`` is non-empty, the request connects to the pre-resolved IP
    address instead of re-resolving DNS, preventing DNS rebinding SSRF.  TLS SNI
    and certificate verification still use the original hostname from the URL.
    """
    out_payload = build_session_webhook_payload(answer, stream_chunk=stream_chunk)
    payload_str = json.dumps(out_payload, ensure_ascii=False)
    host = session_webhook_host(session_webhook)
    timeout_s = 8.0 if stream_chunk else 20.0
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    url = session_webhook.strip()

    if pinned_ip:
        resolver = _PinnedIPResolver(pinned_ip)
        ssl_ctx = ssl.create_default_context()
        connector = aiohttp.TCPConnector(resolver=resolver, ssl=ssl_ctx)
        async with aiohttp.ClientSession(connector=connector) as pinned_session:
            return await _do_post_session_webhook(
                pinned_session, url, payload_str, timeout, host, stream_chunk, pipeline_ctx
            )
    return await _do_post_session_webhook(
        get_outbound_session(), url, payload_str, timeout, host, stream_chunk, pipeline_ctx
    )


async def send_one_reply_chunk(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    session_webhook_valid: Optional[str],
    chunk: str,
    *,
    pipeline_ctx: str = "",
    pinned_ip: str = "",
) -> tuple[bool, bool]:
    """Send one streaming segment: session webhook (text) then OpenAPI ``sampleText`` fallback."""
    logger.debug(
        "[MindBot] outbound_text_chunk %s chars=%s route=%s",
        pipeline_ctx,
        len(chunk),
        "session_webhook" if session_webhook_valid else "openapi_only",
    )
    if session_webhook_valid:
        if await post_session_webhook(
            session_webhook_valid,
            chunk,
            stream_chunk=True,
            pipeline_ctx=pipeline_ctx,
            pinned_ip=pinned_ip,
        ):
            return True, False
        return await reply_via_openapi(cfg, body, chunk, stream_chunk=True, pipeline_ctx=pipeline_ctx)
    return await reply_via_openapi(cfg, body, chunk, stream_chunk=True, pipeline_ctx=pipeline_ctx)
