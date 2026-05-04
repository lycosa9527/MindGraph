"""
Human-readable participant labels for canvas collaboration WebSockets.

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any


def workshop_collab_member_display_name(user: Any) -> str:
    """Resolve a lobby-safe display string (matches profile / Teacher Usage cues)."""
    uid = getattr(user, "id", None)
    try:
        uid_int = int(uid) if uid is not None else 0
    except (TypeError, ValueError):
        uid_int = 0

    for attr in ("name", "username"):
        val = getattr(user, attr, None)
        if val is not None and str(val).strip():
            return str(val).strip()

    phone = getattr(user, "phone", None)
    if phone is not None and str(phone).strip():
        return str(phone).strip()

    email = getattr(user, "email", None)
    if email is not None and str(email).strip():
        local = str(email).strip().split("@", maxsplit=1)[0]
        if local:
            return local

    return f"User {uid_int}" if uid_int else "User ?"
