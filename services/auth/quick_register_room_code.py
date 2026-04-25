"""
HMAC time-window room codes for quick registration (TOTP-style 30s step).

HMAC key material comes from a per-channel ``room_code_secret`` stored in Redis
with the quick-reg token, not from environment variables.

No SMS: attendees enter the 6-digit code shown on the facilitator's modal.

Copyright 2024-2026 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import List, Optional, Tuple

ROOM_CODE_PERIOD_SECONDS = 30


def room_secret_to_hmac_key(room_secret: str) -> bytes:
    """Derive 32-byte HMAC key from the stored per-token secret string."""
    return hashlib.sha256(room_secret.encode("utf-8")).digest()


def room_code_for_step(hmac_key: bytes, token: str, step: int) -> str:
    """Single time-step 6-digit code for the given token and HMAC key."""
    msg = f"{step}\x00{token}".encode("utf-8")
    digest = hmac.new(hmac_key, msg, hashlib.sha256).digest()
    value = int.from_bytes(digest[:4], "big")
    return str(value % 1_000_000).zfill(6)


def current_room_code_from_room_secret(room_secret: str, token: str) -> Tuple[str, int, int, float]:
    """
    Return (display_code, step, next_period_start_unix, server_time).
    next_period_start_unix is the unix timestamp when the next code starts.
    """
    now = time.time()
    step = int(now) // ROOM_CODE_PERIOD_SECONDS
    hkey = room_secret_to_hmac_key(room_secret)
    code = room_code_for_step(hkey, token, step)
    next_start = (step + 1) * ROOM_CODE_PERIOD_SECONDS
    return code, step, next_start, now


def verify_room_code_submitted(
    room_secret: str,
    token: str,
    submitted: str,
    *,
    skew_windows: int = 1,
) -> bool:
    """
    Return True if submitted matches the code for the current or adjacent time steps.
    ``submitted`` should be 6 digit string; caller strips/normalizes.

    All candidate windows are compared (constant-time with respect to which
    window matches) to avoid timing side channels between adjacent steps.
    """
    if len(submitted) != 6 or not submitted.isdigit():
        return False
    hkey = room_secret_to_hmac_key(room_secret)
    step0 = int(time.time()) // ROOM_CODE_PERIOD_SECONDS
    expected: List[str] = []
    for w in range(-skew_windows, skew_windows + 1):
        expected.append(room_code_for_step(hkey, token, step0 + w))
    matches = 0
    for exp in expected:
        matches += hmac.compare_digest(submitted, exp)
    return matches > 0


def time_step_now() -> int:
    """UNIX time step (floor(t/30)) for 30s windows."""
    return int(time.time()) // ROOM_CODE_PERIOD_SECONDS


def next_period_seconds(utc_now: Optional[float] = None) -> int:
    """Seconds until the next 30s boundary."""
    t = time.time() if utc_now is None else utc_now
    step = int(t) // ROOM_CODE_PERIOD_SECONDS
    next_start = (step + 1) * ROOM_CODE_PERIOD_SECONDS
    return max(0, int(round(next_start - t)))
