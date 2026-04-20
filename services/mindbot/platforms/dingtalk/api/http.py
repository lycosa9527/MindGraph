"""Shared HTTP client for ``https://api.dingtalk.com`` (v1.0) JSON APIs."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

import aiohttp

from services.mindbot.infra.http_client import get_dingtalk_api_session
from services.mindbot.platforms.dingtalk.api.constants import DING_API_BASE
from services.mindbot.platforms.dingtalk.api.response import (
    dingtalk_v1_body_log_snippet,
    dingtalk_v1_response_ok,
)

logger = logging.getLogger(__name__)

# Pattern to redact token-like values in logged response snippets.
_SENSITIVE_PATTERN = re.compile(
    r'("(?:accessToken|access_token|token|appSecret|secret|password)")\s*:\s*"[^"]{4,}"',
    re.IGNORECASE,
)


def _sanitize_response_snippet(body_txt: str, max_len: int = 400) -> str:
    """Return a truncated, token-redacted snippet safe for WARNING logs."""
    snippet = body_txt[:max_len]
    return _SENSITIVE_PATTERN.sub(r'\1: "***"', snippet)


def _check_ip_ban_body(body_txt: str, path: str) -> None:
    """Log a distinct warning when the response body looks like a DingTalk IP-level ban.

    DingTalk IP bans (>10 000 calls / 20s from one IP) return a non-JSON body — often
    an HTML page or a JSON blob with ``status: 1111`` and ``punish: deny``.  Because
    the body fails ``json.loads``, the regular QPS-code detection path is bypassed.

    No retry is appropriate here: the ban lasts ~5 minutes and re-trying accelerates
    the problem.  The correct remedy is adding more outbound/egress IPs.
    """
    if not body_txt:
        return
    sample = body_txt[:2000].lower()
    if "punish" in sample or "1111" in sample:
        logger.warning(
            "[MindBot] dingtalk_ip_rate_limit_suspected path=%s body_snippet=%r",
            path,
            body_txt[:200],
        )


async def _v1_json_request(
    method: str,
    path: str,
    access_token: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: int,
    parse_json_on_error: bool,
    verify_response: bool,
) -> tuple[int, Optional[dict[str, Any]]]:
    """Internal helper that executes a POST or PUT JSON request to api.dingtalk.com.

    Args:
        method: HTTP method string, either ``"POST"`` or ``"PUT"``.
        path: API path (appended to DING_API_BASE).
        access_token: Bearer token placed in ``x-acs-dingtalk-access-token``.
        payload: JSON-serialisable request body.
        timeout_seconds: Total aiohttp timeout.
        parse_json_on_error: When True, attempt to parse JSON from non-200 bodies so
            callers can inspect DingTalk business-error fields.
        verify_response: When True, call ``dingtalk_v1_response_ok`` on 200 bodies and
            return ``(status, None)`` when the business result indicates failure.
    """
    url = f"{DING_API_BASE}{path}"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "x-acs-dingtalk-access-token": access_token.strip(),
    }
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    try:
        session = get_dingtalk_api_session()
        request_fn = session.post if method == "POST" else session.put
        async with request_fn(url, headers=headers, json=payload, timeout=timeout, allow_redirects=False) as resp:
            body_txt = await resp.text()
            if resp.status != 200:
                logger.warning(
                    "[MindBot] DingTalk API %s HTTP %s %s",
                    path,
                    resp.status,
                    _sanitize_response_snippet(body_txt),
                )
                if parse_json_on_error and body_txt.strip():
                    try:
                        data_err = json.loads(body_txt)
                    except json.JSONDecodeError:
                        _check_ip_ban_body(body_txt, path)
                        return resp.status, None
                    if isinstance(data_err, dict):
                        return resp.status, data_err
                else:
                    _check_ip_ban_body(body_txt, path)
                return resp.status, None
            try:
                data = json.loads(body_txt)
            except json.JSONDecodeError:
                logger.warning("[MindBot] DingTalk API %s invalid JSON", path)
                return resp.status, None
            if not isinstance(data, dict):
                return resp.status, None
            if verify_response and not dingtalk_v1_response_ok(data):
                logger.warning(
                    "[MindBot] DingTalk API %s business failure: %s",
                    path,
                    dingtalk_v1_body_log_snippet(data),
                )
                return resp.status, None
            return resp.status, data
    except Exception as exc:
        logger.exception(
            "[MindBot] DingTalk API %s network_error: %s: %s",
            path,
            type(exc).__name__,
            exc,
        )
        return 0, None


async def post_v1_json(
    path: str,
    access_token: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: int = 60,
) -> tuple[int, Optional[dict[str, Any]]]:
    """
    POST JSON to ``api.dingtalk.com`` with ``x-acs-dingtalk-access-token``.

    Returns ``(http_status, parsed_json_or_none)``.  ``None`` is returned on
    HTTP errors, JSON parse errors, or when the DingTalk business result
    indicates failure (``success`` false / non-zero ``errcode``).
    """
    return await _v1_json_request(
        "POST",
        path,
        access_token,
        payload,
        timeout_seconds=timeout_seconds,
        parse_json_on_error=False,
        verify_response=True,
    )


async def post_v1_json_unverified(
    path: str,
    access_token: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: int = 60,
    parse_json_on_error: bool = False,
) -> tuple[int, Optional[dict[str, Any]]]:
    """
    POST JSON like ``post_v1_json`` but return parsed body on HTTP 200 even when
    ``success`` is false (for error mapping).

    When ``parse_json_on_error`` is true, non-200 responses with a JSON object
    body are still parsed (DingTalk may return HTTP 400 with business error
    fields in the body).
    """
    return await _v1_json_request(
        "POST",
        path,
        access_token,
        payload,
        timeout_seconds=timeout_seconds,
        parse_json_on_error=parse_json_on_error,
        verify_response=False,
    )


async def put_v1_json(
    path: str,
    access_token: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: int = 60,
) -> tuple[int, Optional[dict[str, Any]]]:
    """
    PUT JSON to ``api.dingtalk.com`` with ``x-acs-dingtalk-access-token``.

    Returns ``(http_status, parsed_json_or_none)``.
    """
    return await _v1_json_request(
        "PUT",
        path,
        access_token,
        payload,
        timeout_seconds=timeout_seconds,
        parse_json_on_error=False,
        verify_response=True,
    )


async def put_v1_json_unverified(
    path: str,
    access_token: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: int = 15,
    parse_json_on_error: bool = False,
) -> tuple[int, Optional[dict[str, Any]]]:
    """
    PUT JSON like ``put_v1_json`` but return parsed body on HTTP 200 even when
    ``success`` is false (for admin probes that expect business errors).

    When ``parse_json_on_error`` is true, non-200 responses with a JSON object
    body are still parsed (DingTalk may return HTTP 400 with business error
    fields in the body).
    """
    return await _v1_json_request(
        "PUT",
        path,
        access_token,
        payload,
        timeout_seconds=timeout_seconds,
        parse_json_on_error=parse_json_on_error,
        verify_response=False,
    )
