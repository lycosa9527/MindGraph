"""
Workshop session expiry: Beijing calendar day and duration presets.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

BEIJING_TZ = ZoneInfo("Asia/Shanghai")

DURATION_1H = "1h"
DURATION_TODAY = "today"
DURATION_2D = "2d"

WORKSHOP_VISIBILITY_ORGANIZATION = "organization"
WORKSHOP_VISIBILITY_NETWORK = "network"

_VALID_ORG = frozenset({DURATION_1H, DURATION_TODAY, DURATION_2D})
_VALID_NETWORK = frozenset({DURATION_TODAY, DURATION_2D})


def duration_allowed_for_visibility(visibility: str, duration: str) -> bool:
    """Return True if duration is allowed for organization vs network mode."""
    if visibility == WORKSHOP_VISIBILITY_NETWORK:
        return duration in _VALID_NETWORK
    if visibility == WORKSHOP_VISIBILITY_ORGANIZATION:
        return duration in _VALID_ORG
    return False


def _as_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def end_of_calendar_day_beijing_utc(from_when: datetime) -> datetime:
    """
    Return UTC instant for end of the same calendar day in Asia/Shanghai
    (23:59:59.999999 Beijing on that day).
    """
    utc = _as_utc_aware(from_when)
    bj = utc.astimezone(BEIJING_TZ)
    next_midnight_bj = datetime.combine(
        bj.date() + timedelta(days=1),
        datetime.min.time(),
        tzinfo=BEIJING_TZ,
    )
    end_bj = next_midnight_bj - timedelta(microseconds=1)
    return end_bj.astimezone(timezone.utc)


def compute_workshop_expires_at(
    start_utc: datetime,
    duration: str,
) -> datetime:
    """
    Compute workshop_expires_at as naive UTC for DB storage.

    Args:
        start_utc: Start time (naive UTC or aware).
        duration: 1h | today | 2d
    """
    start = _as_utc_aware(start_utc)
    if duration == DURATION_1H:
        result = start + timedelta(hours=1)
    elif duration == DURATION_TODAY:
        result = end_of_calendar_day_beijing_utc(start)
    elif duration == DURATION_2D:
        result = start + timedelta(days=2)
    else:
        result = start + timedelta(hours=24)

    naive = result.replace(tzinfo=None)
    return naive


def redis_ttl_seconds_for_expires_at(expires_at_naive_utc: datetime) -> int:
    """Seconds until expiry for Redis setex; at least 1."""
    now = datetime.utcnow()
    if expires_at_naive_utc.tzinfo is not None:
        exp = expires_at_naive_utc.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        exp = expires_at_naive_utc
    delta = (exp - now).total_seconds()
    return max(1, int(delta))


def is_workshop_expired(expires_at_naive_utc: Optional[datetime]) -> bool:
    """True if expiry time is in the past or None treated as unknown (not expired)."""
    if expires_at_naive_utc is None:
        return False
    now = datetime.utcnow()
    return expires_at_naive_utc <= now


def remaining_seconds(expires_at_naive_utc: Optional[datetime]) -> Optional[int]:
    """Seconds until expiry, or None if no expiry set."""
    if expires_at_naive_utc is None:
        return None
    now = datetime.utcnow()
    sec = int((expires_at_naive_utc - now).total_seconds())
    return max(0, sec)
