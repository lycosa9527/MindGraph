"""
Core Infrastructure Routers

Core application infrastructure endpoints including health checks, pages, SPA, and notifications.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from .health import router as health_router
from .pages import router as pages_router
from .update_notification import router as update_notification_router
from .vue_spa import router as vue_spa_router

__all__ = [
    "health_router",
    "pages_router",
    "vue_spa_router",
    "update_notification_router",
]

# Backward compatibility aliases
health = health_router
pages = pages_router
vue_spa = vue_spa_router
update_notification = update_notification_router
