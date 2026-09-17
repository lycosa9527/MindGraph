"""List and kick signed-in browser devices for the account UI.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from services.redis.session.redis_session_manager import (
    get_refresh_token_manager,
    get_session_manager,
)

logger = logging.getLogger(__name__)

DEVICE_ID_PATTERN = re.compile(r"^[a-fA-F0-9]{8,64}$")
KICK_REASON = "device_kick"


class LoginDevicesUnavailableError(Exception):
    """Redis is not available for login-device operations."""


@dataclass(frozen=True)
class LoginDevice:
    """One signed-in browser shown in account info."""

    device_id: str
    label: str
    ip_address: str
    created_at: str
    is_current: bool


def is_login_device_id(device_id: str) -> bool:
    """True when ``device_id`` is a stored device fingerprint."""
    return bool(DEVICE_ID_PATTERN.fullmatch(device_id))


def describe_user_agent(user_agent: str) -> str:
    """Turn a User-Agent string into a short browser · OS label."""
    raw = (user_agent or "").strip()
    if not raw:
        return ""

    lowered = raw.lower()
    browser = _browser_from_user_agent(lowered)
    os_name = _os_from_user_agent(lowered)
    if os_name:
        return f"{browser} · {os_name}"
    return browser


def _browser_from_user_agent(lowered: str) -> str:
    """Pick a browser name from a lowercased User-Agent."""
    if "edg/" in lowered or "edge/" in lowered:
        return "Edge"
    if "opr/" in lowered or "opera" in lowered:
        return "Opera"
    if "firefox/" in lowered or "fxios/" in lowered:
        return "Firefox"
    if "crios/" in lowered:
        return "Chrome"
    if "chrome/" in lowered or "chromium/" in lowered:
        return "Chrome"
    if "safari/" in lowered:
        return "Safari"
    if "mindgraph" in lowered:
        return "MindGraph"
    return "Browser"


def _os_from_user_agent(lowered: str) -> str:
    """Pick an OS name from a lowercased User-Agent."""
    if "iphone" in lowered or "ipad" in lowered or "ipod" in lowered:
        return "iOS"
    if "android" in lowered:
        return "Android"
    if "windows" in lowered:
        return "Windows"
    if "mac os" in lowered or "macintosh" in lowered:
        return "macOS"
    if "cros" in lowered:
        return "ChromeOS"
    if "linux" in lowered:
        return "Linux"
    return ""


def _newer_created_at(left: str, right: str) -> str:
    """Return the later of two ISO timestamps, preferring a non-empty value."""
    if not left:
        return right
    if not right:
        return left
    return left if left >= right else right


def merge_login_device_rows(
    refresh_rows: list[dict[str, str]],
    session_rows: list[dict[str, str]],
    current_device_hash: str,
) -> list[LoginDevice]:
    """Merge refresh tokens and live access sessions by device hash."""
    merged: dict[str, dict[str, str]] = {}
    for row in refresh_rows:
        device_hash = str(row.get("device_hash") or "")
        if not device_hash:
            continue
        existing = merged.get(device_hash)
        if existing is None:
            merged[device_hash] = {
                "label": describe_user_agent(str(row.get("user_agent") or "")),
                "ip_address": str(row.get("ip_address") or ""),
                "created_at": str(row.get("created_at") or ""),
            }
            continue
        existing["created_at"] = _newer_created_at(
            existing["created_at"],
            str(row.get("created_at") or ""),
        )
        if not existing["ip_address"]:
            existing["ip_address"] = str(row.get("ip_address") or "")
        if not existing["label"]:
            existing["label"] = describe_user_agent(str(row.get("user_agent") or ""))

    for row in session_rows:
        device_hash = str(row.get("device_hash") or "")
        if not device_hash:
            continue
        existing = merged.get(device_hash)
        created_at = str(row.get("created_at") or "")
        if existing is None:
            merged[device_hash] = {
                "label": "",
                "ip_address": "",
                "created_at": created_at,
            }
            continue
        existing["created_at"] = _newer_created_at(existing["created_at"], created_at)

    devices = [
        LoginDevice(
            device_id=device_hash,
            label=payload["label"],
            ip_address=payload["ip_address"],
            created_at=payload["created_at"],
            is_current=bool(current_device_hash) and device_hash == current_device_hash,
        )
        for device_hash, payload in merged.items()
    ]
    current = [item for item in devices if item.is_current]
    others = [item for item in devices if not item.is_current]
    others.sort(key=lambda item: item.created_at, reverse=True)
    return [*current, *others]


async def list_login_devices(user_id: int, current_device_hash: str) -> list[LoginDevice]:
    """Return signed-in devices for the account UI."""
    refresh_rows = await get_refresh_token_manager().list_refresh_records(user_id)
    session_rows = await get_session_manager().list_access_session_devices(user_id)
    if refresh_rows is None and session_rows is None:
        raise LoginDevicesUnavailableError("Redis unavailable")
    return merge_login_device_rows(
        refresh_rows or [],
        session_rows or [],
        current_device_hash,
    )


async def kick_login_device(
    user_id: int,
    device_id: str,
    current_ip: str | None,
) -> bool:
    """Revoke refresh tokens and access sessions for one device."""
    if not is_login_device_id(device_id):
        return False

    refresh_rows = await get_refresh_token_manager().list_refresh_records(user_id)
    session_rows = await get_session_manager().list_access_session_devices(user_id)
    if refresh_rows is None and session_rows is None:
        raise LoginDevicesUnavailableError("Redis unavailable")

    known_ids = {str(row.get("device_hash") or "") for row in (refresh_rows or []) + (session_rows or [])}
    if device_id not in known_ids:
        return False

    revoked = await get_refresh_token_manager().revoke_refresh_tokens_for_device(
        user_id,
        device_id,
        reason=KICK_REASON,
    )
    removed = await get_session_manager().invalidate_sessions_for_device(
        user_id,
        device_id,
        ip_address=current_ip,
        reason=KICK_REASON,
    )
    logger.info(
        "[TokenAudit] Device kicked: user=%s, device=%s..., refresh_revoked=%s, sessions=%s",
        user_id,
        device_id[:8],
        revoked,
        removed,
    )
    return True


def login_device_to_dict(device: LoginDevice) -> dict[str, object]:
    """JSON payload for one signed-in device."""
    return {
        "device_id": device.device_id,
        "label": device.label,
        "ip_address": device.ip_address,
        "created_at": device.created_at,
        "is_current": device.is_current,
    }
