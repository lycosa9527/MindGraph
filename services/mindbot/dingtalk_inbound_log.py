"""Optional logging for DingTalk HTTP traffic hitting MindBot callback routes.

Set MINDBOT_LOG_CALLBACK_INBOUND_FULL=1 to log method, client, forwarded headers,
all request headers, and raw body (capped). Use when debugging NPM / TLS / routing.

Set MINDBOT_LOG_CALLBACK_INBOUND=1 for a shorter line (path, query, body preview).
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import Request

from services.mindbot.platforms.dingtalk.verify import extract_dingtalk_robot_auth_headers
from utils.env_helpers import env_bool, env_int

logger = logging.getLogger(__name__)

_PREVIEW_LEN = 2048
_DEFAULT_BODY_LOG_MAX = 65536


def dingtalk_inbound_logging_enabled() -> bool:
    return env_bool("MINDBOT_LOG_CALLBACK_INBOUND", False) or env_bool(
        "MINDBOT_LOG_CALLBACK_INBOUND_FULL",
        False,
    )


def dingtalk_inbound_full_logging() -> bool:
    return env_bool("MINDBOT_LOG_CALLBACK_INBOUND_FULL", False)


def _body_log_max() -> int:
    return max(256, env_int("MINDBOT_LOG_CALLBACK_BODY_MAX", _DEFAULT_BODY_LOG_MAX))


def log_dingtalk_inbound(request: Request, raw: bytes, route_label: str) -> None:
    """
    Log one inbound request. Full mode logs headers and body; compact logs a short preview.

    Does nothing unless MINDBOT_LOG_CALLBACK_INBOUND or MINDBOT_LOG_CALLBACK_INBOUND_FULL is set.
    """
    if not dingtalk_inbound_logging_enabled():
        return
    if dingtalk_inbound_full_logging():
        _log_full(request, raw, route_label)
    else:
        _log_compact(request, raw, route_label)


def _log_compact(request: Request, raw: bytes, route_label: str) -> None:
    ts, sg = extract_dingtalk_robot_auth_headers(request.headers)
    preview = raw.decode("utf-8", errors="replace")[:_PREVIEW_LEN]
    logger.info(
        "[MindBot] inbound %s method=%s path=%s query=%s body_len=%s timestamp=%s sign_len=%s preview=%r",
        route_label,
        request.method,
        request.url.path,
        request.url.query or "",
        len(raw),
        "set" if ts else "missing",
        len(sg or ""),
        preview,
    )


def _log_full(request: Request, raw: bytes, route_label: str) -> None:
    headers_dict = dict(request.headers.items())
    client_host: Optional[str] = None
    if request.client is not None:
        client_host = request.client.host
    xfwd = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    xreal = request.headers.get("x-real-ip") or request.headers.get("X-Real-IP")
    xfproto = request.headers.get("x-forwarded-proto") or request.headers.get("X-Forwarded-Proto")
    max_body = _body_log_max()
    body_snip = raw[:max_body] if len(raw) > max_body else raw
    truncated = len(raw) > max_body
    body_text = body_snip.decode("utf-8", errors="replace")

    logger.info(
        "[MindBot] dingtalk_inbound_full label=%s method=%s path=%s query=%r "
        "client_host=%s x_forwarded_for=%r x_real_ip=%r x_forwarded_proto=%r "
        "body_len=%s body_truncated=%s",
        route_label,
        request.method,
        request.url.path,
        request.url.query or "",
        client_host,
        xfwd,
        xreal,
        xfproto,
        len(raw),
        truncated,
    )
    logger.info(
        "[MindBot] dingtalk_inbound_full label=%s headers_json=%s",
        route_label,
        json.dumps(headers_dict, ensure_ascii=False),
    )
    logger.info("[MindBot] dingtalk_inbound_full label=%s body=%r", route_label, body_text)
