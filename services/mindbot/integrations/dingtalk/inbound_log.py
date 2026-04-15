"""Optional logging for DingTalk HTTP traffic hitting MindBot callback routes.

**Levels (Python ``logging``):**

- **INFO** — One compact line per inbound request when compact mode is enabled
  (``MINDBOT_LOG_CALLBACK_INBOUND=1`` without full debug). Safe for ops dashboards.
- **DEBUG** — Full inbound dumps (headers, raw body, parsed JSON) when
  ``MINDBOT_LOG_CALLBACK_DEBUG`` is on (default) or ``MINDBOT_LOG_CALLBACK_INBOUND_FULL=1``.
  May include secrets; enable only with log aggregation access controls.
- **WARNING** — Rejected callbacks: one summary line (reason, route, sizes, keys).
  Verbose dumps for failures still go to **DEBUG** when debug mode is on.

Set ``MINDBOT_LOG_CALLBACK_DEBUG=0`` to disable full inbound + failure dumps.
When ``MINDBOT_LOG_CALLBACK_DEBUG=0``: set ``MINDBOT_LOG_CALLBACK_INBOUND_FULL=1`` for full
inbound at DEBUG, or ``MINDBOT_LOG_CALLBACK_INBOUND=1`` for one compact **INFO** line per request.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping, Optional

from fastapi import Request

from services.mindbot.platforms.dingtalk.auth.verify import extract_dingtalk_robot_auth_headers
from utils.env_helpers import env_bool, env_int

logger = logging.getLogger(__name__)

_PREVIEW_LEN = 2048
_DEFAULT_BODY_LOG_MAX = 65536
_JSON_LOG_MAX = 65536


def debug_callback_failure_logging_enabled() -> bool:
    """True when MINDBOT_LOG_CALLBACK_DEBUG is unset or truthy (full inbound + failure details)."""
    return env_bool("MINDBOT_LOG_CALLBACK_DEBUG", True)


def dingtalk_inbound_logging_enabled() -> bool:
    return (
        env_bool("MINDBOT_LOG_CALLBACK_INBOUND", False)
        or env_bool("MINDBOT_LOG_CALLBACK_INBOUND_FULL", False)
        or debug_callback_failure_logging_enabled()
    )


def dingtalk_inbound_full_logging() -> bool:
    return env_bool("MINDBOT_LOG_CALLBACK_INBOUND_FULL", False) or (
        debug_callback_failure_logging_enabled()
    )


def _body_log_max() -> int:
    return max(256, env_int("MINDBOT_LOG_CALLBACK_BODY_MAX", _DEFAULT_BODY_LOG_MAX))


def _parsed_body_json_for_log(parsed_body: dict[str, Any]) -> str:
    try:
        parsed_json = json.dumps(
            parsed_body,
            ensure_ascii=False,
            default=str,
        )
    except (TypeError, ValueError):
        parsed_json = repr(parsed_body)
    if len(parsed_json) > _JSON_LOG_MAX:
        parsed_json = parsed_json[:_JSON_LOG_MAX] + "...(truncated)"
    return parsed_json


def log_dingtalk_inbound(
    request: Request,
    raw: bytes,
    route_label: str,
    parsed_body: Optional[dict[str, Any]] = None,
) -> None:
    """
    Log one inbound request. Full mode logs headers, raw body, and optional parsed JSON;
    compact logs a short preview.

    Does nothing when MINDBOT_LOG_CALLBACK_DEBUG=0 and compact/full inbound env vars
    are unset or off.
    """
    if not dingtalk_inbound_logging_enabled():
        return
    if dingtalk_inbound_full_logging():
        _log_full(request, raw, route_label, parsed_body=parsed_body)
    else:
        _log_compact(request, raw, route_label)


def _log_compact(request: Request, raw: bytes, route_label: str) -> None:
    ts, sg = extract_dingtalk_robot_auth_headers(request.headers)
    preview = raw.decode("utf-8", errors="replace")[:_PREVIEW_LEN]
    logger.info(
        "[MindBot] inbound_compact %s method=%s path=%s query=%s body_len=%s "
        "timestamp=%s sign_len=%s preview=%r",
        route_label,
        request.method,
        request.url.path,
        request.url.query or "",
        len(raw),
        "set" if ts else "missing",
        len(sg or ""),
        preview,
    )


def _log_full(
    request: Request,
    raw: bytes,
    route_label: str,
    *,
    parsed_body: Optional[dict[str, Any]] = None,
) -> None:
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

    logger.debug(
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
    logger.debug(
        "[MindBot] dingtalk_inbound_full label=%s headers_json=%s",
        route_label,
        json.dumps(headers_dict, ensure_ascii=False),
    )
    logger.debug("[MindBot] dingtalk_inbound_full label=%s body=%r", route_label, body_text)
    if parsed_body is not None:
        logger.debug(
            "[MindBot] dingtalk_inbound_full label=%s body_parsed_json=%s",
            route_label,
            _parsed_body_json_for_log(parsed_body),
        )


def log_dingtalk_callback_failure_details(
    *,
    route_label: str,
    headers: Mapping[str, str],
    raw_body: bytes,
    parsed_body: dict[str, Any],
    reason: str,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """
    Log callback rejection: **WARNING** summary, **DEBUG** for headers/body when debug mode is on.

    Skipped when MINDBOT_LOG_CALLBACK_DEBUG=0 (default is on). Safe only when debug_raw_body was captured.
    """
    if not debug_callback_failure_logging_enabled():
        return
    hdr_copy = dict(headers)
    ts, sg = extract_dingtalk_robot_auth_headers(headers)
    max_body = _body_log_max()
    body_snip = raw_body[:max_body] if len(raw_body) > max_body else raw_body
    truncated = len(raw_body) > max_body
    body_text = body_snip.decode("utf-8", errors="replace")
    parsed_json = _parsed_body_json_for_log(parsed_body)

    top_keys = sorted(parsed_body.keys())
    logger.warning(
        "[MindBot] callback_rejected reason=%s route=%s body_len=%s raw_truncated=%s "
        "timestamp_header=%s sign_header_len=%s parsed_top_keys=%s extra=%s",
        reason,
        route_label,
        len(raw_body),
        truncated,
        "set" if ts else "missing",
        len(sg or ""),
        top_keys[:80],
        extra or {},
    )
    logger.debug(
        "[MindBot] callback_rejected_details route=%s headers_json=%s",
        route_label,
        json.dumps(hdr_copy, ensure_ascii=False),
    )
    logger.debug("[MindBot] callback_rejected_details route=%s body_raw=%r", route_label, body_text)
    logger.debug(
        "[MindBot] callback_rejected_details route=%s body_parsed_json=%s",
        route_label,
        parsed_json,
    )
