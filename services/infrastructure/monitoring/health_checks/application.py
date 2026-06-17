"""Application component health check callables.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from config.settings import config
from services.infrastructure.lifecycle.app_runtime import get_uptime_seconds

logger = logging.getLogger(__name__)


async def check_application_health() -> Dict[str, Any]:
    """Check application health status without importing ``main``."""
    try:
        return {
            "status": "healthy",
            "version": config.version,
            "uptime_seconds": round(get_uptime_seconds(), 1),
        }
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        logger.error("Application health check failed: %s", exc, exc_info=True)
        return {"status": "error", "error": str(exc)}
