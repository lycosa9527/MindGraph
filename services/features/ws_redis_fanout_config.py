"""
Configuration for Redis WebSocket fan-out (multi-worker).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os

from services.redis.redis_client import is_redis_available

CHAT_FANOUT_CHANNEL = "mg:ws:chat:fanout"
WORKSHOP_FANOUT_CHANNEL = "mg:ws:workshop:fanout"
ENVELOPE_VERSION = 1


def is_ws_fanout_enabled() -> bool:
    """Return True when Redis pub/sub fan-out is enabled."""
    if os.getenv("WS_REDIS_FANOUT_ENABLED", "true").lower() not in (
        "1", "true", "yes",
    ):
        return False
    try:
        return is_redis_available()
    except ImportError:
        return False
