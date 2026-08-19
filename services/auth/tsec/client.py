"""Async DescribeCaptchaResult via TC3-HMAC-SHA256 (no Tencent SDK)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from services.auth.tsec.config import (
    tencent_captcha_app_id,
    tencent_captcha_app_secret_key,
    tencent_captcha_business_id,
    tencent_captcha_scene_id,
    tencent_captcha_secret_id,
    tencent_captcha_secret_key,
)
from services.utils.error_types import JSON_PARSE_ERRORS

logger = logging.getLogger(__name__)

CAPTCHA_HOST = "captcha.tencentcloudapi.com"
CAPTCHA_SERVICE = "captcha"
CAPTCHA_VERSION = "2019-07-22"
CAPTCHA_ACTION = "DescribeCaptchaResult"
CAPTCHA_TYPE = 9
REQUEST_TIMEOUT_SECONDS = 5.0


class TsecCaptchaClientError(Exception):
    """DescribeCaptchaResult transport or Cloud API error."""


def _sign(key: bytes, msg: str) -> bytes:
    """HMAC-SHA256 digest for one TC3 signing step."""
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _build_authorization(timestamp: int, payload: str) -> str:
    """Build the TC3 Authorization header for DescribeCaptchaResult."""
    secret_id = tencent_captcha_secret_id()
    secret_key = tencent_captcha_secret_key()
    date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
    content_type = "application/json"
    canonical_headers = f"content-type:{content_type}\nhost:{CAPTCHA_HOST}\nx-tc-action:{CAPTCHA_ACTION.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"
    algorithm = "TC3-HMAC-SHA256"
    credential_scope = f"{date}/{CAPTCHA_SERVICE}/tc3_request"
    hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashed_canonical}"
    secret_date = _sign(f"TC3{secret_key}".encode("utf-8"), date)
    secret_service = _sign(secret_date, CAPTCHA_SERVICE)
    secret_signing = _sign(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return (
        f"{algorithm} Credential={secret_id}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
    )


def _parse_captcha_app_id() -> int:
    """Parse CaptchaAppId as the integer DescribeCaptchaResult requires."""
    raw = tencent_captcha_app_id()
    try:
        return int(raw)
    except ValueError as exc:
        raise TsecCaptchaClientError(f"Invalid TENCENT_CAPTCHA_APP_ID: {raw!r}") from exc


def build_describe_captcha_body(ticket: str, randstr: str, user_ip: str) -> dict[str, Any]:
    """Build every documented DescribeCaptchaResult input we can populate.

    NeedGetCaptchaTime=1 so GetCaptchaTime is returned. BusinessId/SceneId are
    reserved and sent only when configured. MacAddress/Imei are mobile-only and
    are omitted on the web path.
    """
    body: dict[str, Any] = {
        "CaptchaType": CAPTCHA_TYPE,
        "Ticket": ticket,
        "UserIp": user_ip,
        "Randstr": randstr,
        "CaptchaAppId": _parse_captcha_app_id(),
        "AppSecretKey": tencent_captcha_app_secret_key(),
        "NeedGetCaptchaTime": 1,
    }
    business_id = tencent_captcha_business_id()
    if business_id is not None:
        body["BusinessId"] = business_id
    scene_id = tencent_captcha_scene_id()
    if scene_id is not None:
        body["SceneId"] = scene_id
    return body


async def describe_captcha_result(
    ticket: str,
    randstr: str,
    user_ip: str,
    client: Optional[httpx.AsyncClient] = None,
) -> dict[str, Any]:
    """Call DescribeCaptchaResult and return the Response object.

    Raises TsecCaptchaClientError on timeout, HTTP failure, or Cloud API Error.
    """
    body = build_describe_captcha_body(ticket, randstr, user_ip)
    payload = json.dumps(body)
    timestamp = int(time.time())
    headers = {
        "Authorization": _build_authorization(timestamp, payload),
        "Content-Type": "application/json",
        "Host": CAPTCHA_HOST,
        "X-TC-Action": CAPTCHA_ACTION,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": CAPTCHA_VERSION,
    }
    endpoint = f"https://{CAPTCHA_HOST}"
    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS))
    try:
        response = await http_client.post(endpoint, content=payload, headers=headers)
    except httpx.TimeoutException as exc:
        logger.error("T-Sec DescribeCaptchaResult timeout")
        raise TsecCaptchaClientError("timeout") from exc
    except httpx.HTTPError as exc:
        logger.error("T-Sec DescribeCaptchaResult HTTP error: %s", exc)
        raise TsecCaptchaClientError("http_error") from exc
    finally:
        if owns_client:
            await http_client.aclose()

    if response.status_code != 200:
        logger.error(
            "T-Sec DescribeCaptchaResult non-200: %s %s",
            response.status_code,
            response.text[:200],
        )
        raise TsecCaptchaClientError("http_status")

    try:
        result = response.json()
    except JSON_PARSE_ERRORS as exc:
        logger.error("T-Sec DescribeCaptchaResult JSON parse error: %s", exc)
        raise TsecCaptchaClientError("invalid_json") from exc

    resp_data = result.get("Response")
    if not isinstance(resp_data, dict):
        raise TsecCaptchaClientError("invalid_response")

    error = resp_data.get("Error")
    if isinstance(error, dict):
        error_code = str(error.get("Code", "Unknown"))
        logger.error(
            "T-Sec Cloud API error: code=%s msg=%s request_id=%s",
            error_code,
            error.get("Message", ""),
            resp_data.get("RequestId"),
        )
        raise TsecCaptchaClientError(error_code)

    return resp_data
