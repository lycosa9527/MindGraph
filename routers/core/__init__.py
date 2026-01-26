"""
Core Infrastructure Routers

Core application infrastructure endpoints including caching, health checks, pages, SPA, and notifications.
"""

from .cache import router as cache_router
from .health import router as health_router
from .pages import router as pages_router
from .vue_spa import router as vue_spa_router
from .update_notification import router as update_notification_router

__all__ = [
    "cache_router",
    "health_router",
    "pages_router",
    "vue_spa_router",
    "update_notification_router",
]

# Backward compatibility aliases
cache = cache_router
health = health_router
pages = pages_router
vue_spa = vue_spa_router
update_notification = update_notification_router
