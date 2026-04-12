"""DingTalk HTTP callback signature verification (receive-message-1 protocol)."""

import base64
import hashlib
import hmac
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_SKEW_SECONDS = 3600


def compute_sign(timestamp_str: str, app_secret: str) -> str:
    """Return Base64(HMAC-SHA256) per DingTalk official Python sample."""
    app_secret_enc = app_secret.encode("utf-8")
    string_to_sign = f"{timestamp_str}\n{app_secret}"
    string_to_sign_enc = string_to_sign.encode("utf-8")
    digest = hmac.new(app_secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def verify_dingtalk_sign(
    timestamp_str: Optional[str],
    sign_header: Optional[str],
    app_secret: str,
    now_ts: Optional[float] = None,
) -> bool:
    """
    Verify timestamp and sign from HTTP headers.

    Reject if timestamp missing, skew > 1 hour, or sign mismatch.
    """
    if not timestamp_str or not sign_header or not app_secret:
        return False
    try:
        ts_ms = int(timestamp_str)
    except (TypeError, ValueError):
        return False
    now_ms = int((now_ts if now_ts is not None else time.time()) * 1000)
    if abs(now_ms - ts_ms) > _MAX_SKEW_SECONDS * 1000:
        logger.warning("[MindBot] DingTalk timestamp skew too large")
        return False
    expected = compute_sign(timestamp_str, app_secret)
    if len(expected) != len(sign_header):
        return False
    return hmac.compare_digest(expected, sign_header)
