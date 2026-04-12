"""DingTalk HTTP callback signature verification (receive-message-1 protocol).

Matches DingTalk docs and common Flask samples: ``Base64(HmacSHA256(key=app_secret,
msg=timestamp + "\\n" + app_secret))``, timestamp skew window (default 1 hour in ms).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from typing import Any, Optional

from utils.env_helpers import env_int

logger = logging.getLogger(__name__)

_DEFAULT_MAX_SKEW_MS = 3600000
_MAX_SKEW_MS_CAP = 86400000


def _max_skew_ms() -> int:
    raw = env_int("MINDBOT_DINGTALK_MAX_SKEW_MS", _DEFAULT_MAX_SKEW_MS)
    if raw < 1:
        return _DEFAULT_MAX_SKEW_MS
    return min(raw, _MAX_SKEW_MS_CAP)


def extract_dingtalk_robot_auth_headers(headers: Any) -> tuple[Optional[str], Optional[str]]:
    """
    Read ``timestamp`` and ``sign`` for receive-message-1 (same names as DingTalk / Flask samples).

    Starlette header lookup is case-insensitive; alternate spellings are listed for clarity.
    """
    ts_raw = headers.get("timestamp") or headers.get("Timestamp")
    sg_raw = headers.get("sign") or headers.get("Sign")
    ts = ts_raw.strip() if isinstance(ts_raw, str) else None
    sg = sg_raw.strip() if isinstance(sg_raw, str) else None
    if ts == "":
        ts = None
    if sg == "":
        sg = None
    return ts, sg


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

    Reject if timestamp missing, skew over configured window, or sign mismatch.
    """
    ts = (timestamp_str or "").strip() if isinstance(timestamp_str, str) else ""
    sg = (sign_header or "").strip() if isinstance(sign_header, str) else ""
    secret = (app_secret or "").strip()
    if not ts or not sg or not secret:
        return False
    try:
        ts_ms = int(ts)
    except (TypeError, ValueError):
        return False
    now_ms = int((now_ts if now_ts is not None else time.time()) * 1000)
    max_skew = _max_skew_ms()
    if abs(now_ms - ts_ms) > max_skew:
        logger.warning("[MindBot] DingTalk timestamp skew too large")
        return False
    expected = compute_sign(ts, secret)
    if len(expected) != len(sg):
        return False
    return hmac.compare_digest(expected, sg)
