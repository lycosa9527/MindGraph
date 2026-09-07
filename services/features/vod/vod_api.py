"""Async Tencent VOD Cloud API (2018-07-17) via TC3-HMAC-SHA256.

No official SDK. Host: vod.tencentcloudapi.com.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from services.features.vod.credentials import TencentVodCredentials
from services.utils.error_types import JSON_PARSE_ERRORS

logger = logging.getLogger(__name__)

VOD_HOST = "vod.tencentcloudapi.com"
VOD_SERVICE = "vod"
VOD_VERSION = "2018-07-17"
REQUEST_TIMEOUT_SECONDS = 15.0


class TencentVodApiError(Exception):
    """Cloud API transport or Error payload."""


def _sign(key: bytes, msg: str) -> bytes:
    """HMAC-SHA256 digest for one TC3 signing step."""
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def build_vod_authorization(
    secret_id: str,
    secret_key: str,
    action: str,
    timestamp: int,
    payload: str,
) -> str:
    """Build the TC3 Authorization header for a VOD action."""
    date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
    content_type = "application/json"
    canonical_headers = f"content-type:{content_type}\nhost:{VOD_HOST}\nx-tc-action:{action.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"
    algorithm = "TC3-HMAC-SHA256"
    credential_scope = f"{date}/{VOD_SERVICE}/tc3_request"
    hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashed_canonical}"
    secret_date = _sign(f"TC3{secret_key}".encode("utf-8"), date)
    secret_service = _sign(secret_date, VOD_SERVICE)
    secret_signing = _sign(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return (
        f"{algorithm} Credential={secret_id}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
    )


async def call_vod_api(
    credentials: TencentVodCredentials,
    action: str,
    body: dict[str, Any],
    client: Optional[httpx.AsyncClient] = None,
) -> dict[str, Any]:
    """POST one VOD action and return the Response object."""
    payload_obj = dict(body)
    payload_obj["SubAppId"] = credentials.app_id
    payload = json.dumps(payload_obj, separators=(",", ":"), ensure_ascii=False)
    timestamp = int(time.time())
    headers = {
        "Authorization": build_vod_authorization(
            credentials.secret_id,
            credentials.secret_key,
            action,
            timestamp,
            payload,
        ),
        "Content-Type": "application/json",
        "Host": VOD_HOST,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": VOD_VERSION,
        "X-TC-Region": credentials.region,
    }
    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS))
    try:
        response = await http_client.post(f"https://{VOD_HOST}", content=payload, headers=headers)
    except httpx.TimeoutException as exc:
        logger.error("VOD %s timeout", action)
        raise TencentVodApiError("timeout") from exc
    except httpx.HTTPError as exc:
        logger.error("VOD %s HTTP error: %s", action, exc)
        raise TencentVodApiError("http_error") from exc
    finally:
        if owns_client:
            await http_client.aclose()

    if response.status_code != 200:
        logger.error("VOD %s non-200: %s %s", action, response.status_code, response.text[:200])
        raise TencentVodApiError("http_status")

    try:
        result = response.json()
    except JSON_PARSE_ERRORS as exc:
        logger.error("VOD %s JSON parse error: %s", action, exc)
        raise TencentVodApiError("invalid_json") from exc

    resp_data = result.get("Response")
    if not isinstance(resp_data, dict):
        raise TencentVodApiError("invalid_response")

    error = resp_data.get("Error")
    if isinstance(error, dict):
        error_code = str(error.get("Code", "Unknown"))
        logger.error(
            "VOD Cloud API error: action=%s code=%s msg=%s request_id=%s",
            action,
            error_code,
            error.get("Message", ""),
            resp_data.get("RequestId"),
        )
        raise TencentVodApiError(error_code)

    return resp_data


async def describe_media_infos(
    credentials: TencentVodCredentials,
    file_ids: list[str],
    client: Optional[httpx.AsyncClient] = None,
) -> dict[str, Any]:
    """DescribeMediaInfos for one or more FileIds."""
    return await call_vod_api(
        credentials,
        "DescribeMediaInfos",
        {"FileIds": file_ids},
        client=client,
    )


async def search_media(
    credentials: TencentVodCredentials,
    keyword: str,
    offset: int = 0,
    limit: int = 20,
    client: Optional[httpx.AsyncClient] = None,
) -> dict[str, Any]:
    """SearchMedia by name/keyword (Tencent-side; catalog list uses PG)."""
    return await call_vod_api(
        credentials,
        "SearchMedia",
        {"Name": keyword, "Offset": offset, "Limit": limit},
        client=client,
    )


async def delete_media(
    credentials: TencentVodCredentials,
    file_id: str,
    client: Optional[httpx.AsyncClient] = None,
) -> dict[str, Any]:
    """DeleteMedia on Tencent (best-effort from catalog)."""
    return await call_vod_api(
        credentials,
        "DeleteMedia",
        {"FileId": file_id},
        client=client,
    )


def parse_media_info_set(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Return MediaInfoSet items from DescribeMediaInfos."""
    raw = response.get("MediaInfoSet")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def duration_ms_from_media_info(info: dict[str, Any]) -> Optional[int]:
    """Prefer MetaData.Duration, else BasicInfo.Duration, as milliseconds."""
    for key in ("MetaData", "BasicInfo"):
        block = info.get(key)
        if not isinstance(block, dict):
            continue
        duration = block.get("Duration")
        if isinstance(duration, (int, float)) and duration >= 0:
            return int(round(float(duration) * 1000))
    return None


def catalog_status_from_media_info(info: dict[str, Any]) -> str:
    """Map Tencent BasicInfo.Status to catalog status."""
    basic = info.get("BasicInfo")
    if not isinstance(basic, dict):
        return "processing"
    status = str(basic.get("Status") or "").strip()
    if status in {"Normal", "NormalForbidden"}:
        return "ready"
    if status in {"Forbidden", "Abnormal"}:
        return "failed"
    return "processing"
