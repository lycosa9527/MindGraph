"""DingTalk open-platform HTTP event subscription (``encrypt`` body + query signature)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.errors import MindbotErrorCode, mindbot_error_headers
from services.mindbot.platforms.dingtalk.inbound.oa_callback_crypto import DingTalkOaCallbackCrypto

logger = logging.getLogger(__name__)


def is_dingtalk_platform_event_request(request: Request, body: dict[str, Any]) -> bool:
    """
    True when the request matches DingTalk open-platform callback shape.

    Robot HTTP receive uses ``timestamp`` / ``sign`` headers; event subscription uses
    query ``signature`` (or ``msg_signature``), ``timestamp``, ``nonce`` and JSON ``encrypt``.
    """
    enc = body.get("encrypt")
    if not isinstance(enc, str) or not enc.strip():
        return False
    q = request.query_params
    sig = (q.get("signature") or q.get("msg_signature") or "").strip()
    ts = (q.get("timestamp") or "").strip()
    nonce = (q.get("nonce") or "").strip()
    return bool(sig and ts and nonce)


def dingtalk_platform_event_response(
    request: Request,
    body: dict[str, Any],
    cfg: OrganizationMindbotConfig,
) -> Response:
    """
    Decrypt inbound payload and return encrypted ``success`` JSON (official SDK behavior).

    See: https://github.com/open-dingtalk/DingTalk-Callback-Crypto
    """
    q = request.query_params
    msg_sig = (q.get("signature") or q.get("msg_signature") or "").strip()
    ts = (q.get("timestamp") or "").strip()
    nonce = (q.get("nonce") or "").strip()
    enc = body.get("encrypt")
    if not isinstance(enc, str) or not enc.strip():
        return Response(
            status_code=400,
            headers=mindbot_error_headers(MindbotErrorCode.INVALID_BODY),
        )

    token = (cfg.dingtalk_event_token or "").strip()
    aes_key = (cfg.dingtalk_event_aes_key or "").strip()
    owner_key = (cfg.dingtalk_event_owner_key or "").strip()
    if not token or not aes_key or not owner_key:
        return Response(
            status_code=503,
            headers=mindbot_error_headers(
                MindbotErrorCode.EVENT_PLATFORM_NOT_CONFIGURED,
                organization_id=cfg.organization_id,
                robot_code=cfg.dingtalk_robot_code.strip(),
            ),
        )

    crypto = DingTalkOaCallbackCrypto(token, aes_key, owner_key)
    try:
        plaintext = crypto.get_decrypt_msg(msg_sig, ts, nonce, enc.strip())
    except ValueError:
        return Response(
            status_code=401,
            headers=mindbot_error_headers(
                MindbotErrorCode.EVENT_PLATFORM_DECRYPT_FAILED,
                organization_id=cfg.organization_id,
                robot_code=cfg.dingtalk_robot_code.strip(),
            ),
        )

    logger.debug(
        "[MindBot] event_subscription_decrypt_ok org_id=%s plaintext_len=%s",
        cfg.organization_id,
        len(plaintext),
    )
    payload = crypto.get_encrypted_map("success")
    return JSONResponse(content=payload)


def shared_url_platform_event_error() -> Response:
    """Event subscription needs the per-bot token callback URL (/dingtalk/callback/t/<token>)."""
    return Response(
        status_code=400,
        headers=mindbot_error_headers(MindbotErrorCode.EVENT_USE_PER_ORG_URL),
    )
