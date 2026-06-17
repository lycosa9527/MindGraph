"""Process monitor health check callables.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from services.infrastructure.monitoring.process_monitor import get_process_monitor

logger = logging.getLogger(__name__)


async def check_processes_health() -> Dict[str, Any]:
    """Check process monitor health status."""
    try:
        process_monitor = get_process_monitor()
        status = process_monitor.get_status()

        unhealthy_count = sum(1 for service_status in status.values() if service_status.get("status") == "unhealthy")
        degraded_count = sum(1 for service_status in status.values() if service_status.get("status") == "degraded")

        overall_status = "healthy"
        if unhealthy_count > 0:
            overall_status = "unhealthy"
        elif degraded_count > 0:
            overall_status = "degraded"

        return {
            "status": overall_status,
            "services": status,
            "unhealthy_count": unhealthy_count,
            "degraded_count": degraded_count,
            "total_services": len(status),
        }
    except ImportError:
        return {"status": "unavailable", "message": "Process monitor not available"}
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        logger.error("Process health check failed: %s", exc, exc_info=True)
        return {"status": "error", "error": str(exc)}


def processes_health_payload() -> Dict[str, Any]:
    """Build process monitor payload for the dedicated /health/processes route."""
    process_monitor = get_process_monitor()
    status = process_monitor.get_status()

    unhealthy_count = sum(1 for service_status in status.values() if service_status.get("status") == "unhealthy")
    degraded_count = sum(1 for service_status in status.values() if service_status.get("status") == "degraded")

    overall_status = "healthy"
    status_code = 200
    if unhealthy_count > 0:
        overall_status = "unhealthy"
        status_code = 503
    elif degraded_count > 0:
        overall_status = "degraded"
        status_code = 503

    return {
        "status": overall_status,
        "services": status,
        "unhealthy_count": unhealthy_count,
        "degraded_count": degraded_count,
        "total_services": len(status),
        "status_code": status_code,
    }
