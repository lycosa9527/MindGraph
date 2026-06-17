"""Health check registry for the health router.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from services.infrastructure.monitoring.health_checks.application import check_application_health
from services.infrastructure.monitoring.health_checks.processes import check_processes_health

HEALTH_CHECK_REGISTRY = {
    "application": check_application_health,
    "processes": check_processes_health,
}

__all__ = ["HEALTH_CHECK_REGISTRY", "check_application_health", "check_processes_health"]
