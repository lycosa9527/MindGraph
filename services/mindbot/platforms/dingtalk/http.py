"""Shared HTTP client for ``https://api.dingtalk.com`` (v1.0) JSON APIs."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional, Tuple

import aiohttp

from services.mindbot.http_client import get_dingtalk_api_session
from services.mindbot.platforms.dingtalk.constants import DING_API_BASE
from services.mindbot.platforms.dingtalk.response import (
    dingtalk_v1_body_log_snippet,
    dingtalk_v1_response_ok,
)

logger = logging.getLogger(__name__)


async def post_v1_json(
    path: str,
    access_token: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: int = 60,
) -> Tuple[int, Optional[dict[str, Any]]]:
    """
    POST JSON to ``api.dingtalk.com`` with ``x-acs-dingtalk-access-token``.

    Returns ``(http_status, parsed_json_or_none)``.
    """
    url = f"{DING_API_BASE}{path}"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "x-acs-dingtalk-access-token": access_token.strip(),
    }
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    try:
        session = get_dingtalk_api_session()
        async with session.post(url, headers=headers, json=payload, timeout=timeout) as resp:
            body_txt = await resp.text()
            if resp.status != 200:
                logger.warning(
                    "[MindBot] DingTalk API %s HTTP %s %s",
                    path,
                    resp.status,
                    body_txt[:500],
                )
                return resp.status, None
            try:
                data = json.loads(body_txt)
            except json.JSONDecodeError:
                logger.warning("[MindBot] DingTalk API %s invalid JSON", path)
                return resp.status, None
            if not isinstance(data, dict):
                return resp.status, None
            if not dingtalk_v1_response_ok(data):
                logger.warning(
                    "[MindBot] DingTalk API %s business failure: %s",
                    path,
                    dingtalk_v1_body_log_snippet(data),
                )
                return resp.status, None
            return resp.status, data
    except Exception as exc:
        logger.exception("[MindBot] DingTalk API %s error: %s", path, exc)
        return 0, None


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
    url = f"{DING_API_BASE}{path}"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "x-acs-dingtalk-access-token": access_token.strip(),
    }
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    try:
        session = get_dingtalk_api_session()
        async with session.post(url, headers=headers, json=payload, timeout=timeout) as resp:
            body_txt = await resp.text()
            if resp.status != 200:
                logger.warning(
                    "[MindBot] DingTalk API %s HTTP %s %s",
                    path,
                    resp.status,
                    body_txt[:500],
                )
                if parse_json_on_error and body_txt.strip():
                    try:
                        data_err = json.loads(body_txt)
                    except json.JSONDecodeError:
                        return resp.status, None
                    if isinstance(data_err, dict):
                        return resp.status, data_err
                return resp.status, None
            try:
                data = json.loads(body_txt)
            except json.JSONDecodeError:
                logger.warning("[MindBot] DingTalk API %s invalid JSON", path)
                return resp.status, None
            if not isinstance(data, dict):
                return resp.status, None
            return resp.status, data
    except Exception as exc:
        logger.exception("[MindBot] DingTalk API %s error: %s", path, exc)
        return 0, None


async def put_v1_json(
    path: str,
    access_token: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: int = 60,
) -> Tuple[int, Optional[dict[str, Any]]]:
    """
    PUT JSON to ``api.dingtalk.com`` with ``x-acs-dingtalk-access-token``.

    Returns ``(http_status, parsed_json_or_none)``.
    """
    url = f"{DING_API_BASE}{path}"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "x-acs-dingtalk-access-token": access_token.strip(),
    }
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    try:
        session = get_dingtalk_api_session()
        async with session.put(url, headers=headers, json=payload, timeout=timeout) as resp:
            body_txt = await resp.text()
            if resp.status != 200:
                logger.warning(
                    "[MindBot] DingTalk API %s HTTP %s %s",
                    path,
                    resp.status,
                    body_txt[:500],
                )
                return resp.status, None
            try:
                data = json.loads(body_txt)
            except json.JSONDecodeError:
                logger.warning("[MindBot] DingTalk API %s invalid JSON", path)
                return resp.status, None
            if not isinstance(data, dict):
                return resp.status, None
            if not dingtalk_v1_response_ok(data):
                logger.warning(
                    "[MindBot] DingTalk API %s business failure: %s",
                    path,
                    dingtalk_v1_body_log_snippet(data),
                )
                return resp.status, None
            return resp.status, data
    except Exception as exc:
        logger.exception("[MindBot] DingTalk API %s error: %s", path, exc)
        return 0, None


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
    url = f"{DING_API_BASE}{path}"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "x-acs-dingtalk-access-token": access_token.strip(),
    }
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    try:
        session = get_dingtalk_api_session()
        async with session.put(url, headers=headers, json=payload, timeout=timeout) as resp:
            body_txt = await resp.text()
            if resp.status != 200:
                logger.warning(
                    "[MindBot] DingTalk API %s HTTP %s %s",
                    path,
                    resp.status,
                    body_txt[:500],
                )
                if parse_json_on_error and body_txt.strip():
                    try:
                        data_err = json.loads(body_txt)
                    except json.JSONDecodeError:
                        return resp.status, None
                    if isinstance(data_err, dict):
                        return resp.status, data_err
                return resp.status, None
            try:
                data = json.loads(body_txt)
            except json.JSONDecodeError:
                logger.warning("[MindBot] DingTalk API %s invalid JSON", path)
                return resp.status, None
            if not isinstance(data, dict):
                return resp.status, None
            return resp.status, data
    except Exception as exc:
        logger.exception("[MindBot] DingTalk API %s error: %s", path, exc)
        return 0, None
