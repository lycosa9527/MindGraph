"""
Shared timeout and limit constants for the online collab hot paths.

No wrapper functions — callers use ``asyncio.timeout`` directly:

    async with asyncio.timeout(DEFAULT_REDIS_HOT_PATH_TIMEOUT_SEC):
        result = await some_redis_call(...)

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

DEFAULT_REDIS_HOT_PATH_TIMEOUT_SEC: float = 2.0
DEFAULT_DB_HOT_PATH_TIMEOUT_SEC: float = 3.0
