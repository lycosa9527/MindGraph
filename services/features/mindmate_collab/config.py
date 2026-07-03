"""
MindMate collab configuration constants.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os

from services.online_collab.core.online_collab_code import ONLINE_COLLAB_CODE_RE
from services.online_collab.lifecycle.online_collab_expiry import (
    DURATION_TODAY,
    DURATION_1H,
    DURATION_2D,
)
from services.features.mindmate_collab.redis_keys import (
    MINDMATE_COLLAB_FANOUT_ROOM_PREFIX,
    MINDMATE_COLLAB_REDIS_PREFIX,
)

MINDMATE_COLLAB_CODE_RE = ONLINE_COLLAB_CODE_RE
MINDMATE_COLLAB_DEFAULT_DURATION = DURATION_TODAY
MINDMATE_COLLAB_SNAPSHOT_MESSAGE_LIMIT = 100


def _parse_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return max(minimum, min(parsed, maximum))


MINDMATE_COLLAB_MAX_PARTICIPANTS = _parse_int_env(
    "MINDMATE_COLLAB_MAX_PARTICIPANTS",
    50,
    2,
    500,
)
MINDMATE_COLLAB_ZOMBIE_GRACE_SECONDS = _parse_int_env(
    "MINDMATE_COLLAB_ZOMBIE_GRACE_SECONDS",
    1800,
    60,
    86400,
)
MINDMATE_COLLAB_IDLE_SILENCE_SECONDS = _parse_int_env(
    "MINDMATE_COLLAB_IDLE_SILENCE_SECONDS",
    1800,
    60,
    86400,
)
MINDMATE_COLLAB_IDLE_GRACE_SECONDS = _parse_int_env(
    "MINDMATE_COLLAB_IDLE_GRACE_SECONDS",
    120,
    30,
    3600,
)
MINDMATE_COLLAB_MONITOR_INTERVAL_SECONDS = _parse_int_env(
    "MINDMATE_COLLAB_MONITOR_INTERVAL_SECONDS",
    15,
    5,
    120,
)
MINDMATE_COLLAB_JOIN_RESUME_TTL_SEC = _parse_int_env(
    "MINDMATE_COLLAB_JOIN_RESUME_TTL_SEC",
    900,
    120,
    86400,
)
MINDMATE_COLLAB_SESSION_TTL = 86400
MINDMATE_COLLAB_PARTICIPANTS_TTL = 3600
MINDMATE_COLLAB_CLOSING_TTL_SEC = 120
MINDMATE_COLLAB_DIFY_STREAM_TTL_SEC = 600
MINDMATE_COLLAB_MAX_CHAT_CONTENT_CHARS = _parse_int_env(
    "MINDMATE_COLLAB_MAX_CHAT_CONTENT_CHARS",
    8000,
    256,
    65536,
)

__all__ = [
    "DURATION_1H",
    "DURATION_2D",
    "DURATION_TODAY",
    "MINDMATE_COLLAB_CLOSING_TTL_SEC",
    "MINDMATE_COLLAB_CODE_RE",
    "MINDMATE_COLLAB_DEFAULT_DURATION",
    "MINDMATE_COLLAB_DIFY_STREAM_TTL_SEC",
    "MINDMATE_COLLAB_FANOUT_ROOM_PREFIX",
    "MINDMATE_COLLAB_IDLE_GRACE_SECONDS",
    "MINDMATE_COLLAB_IDLE_SILENCE_SECONDS",
    "MINDMATE_COLLAB_JOIN_RESUME_TTL_SEC",
    "MINDMATE_COLLAB_MAX_CHAT_CONTENT_CHARS",
    "MINDMATE_COLLAB_MAX_PARTICIPANTS",
    "MINDMATE_COLLAB_MONITOR_INTERVAL_SECONDS",
    "MINDMATE_COLLAB_PARTICIPANTS_TTL",
    "MINDMATE_COLLAB_REDIS_PREFIX",
    "MINDMATE_COLLAB_SESSION_TTL",
    "MINDMATE_COLLAB_SNAPSHOT_MESSAGE_LIMIT",
    "MINDMATE_COLLAB_ZOMBIE_GRACE_SECONDS",
]
