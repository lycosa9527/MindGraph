"""
Admin Routers

Admin-related endpoints for environment settings, logs, and realtime monitoring.
"""

from .env import router as env_router
from .logs import router as logs_router
from .realtime import router as realtime_router

__all__ = [
    "env_router",
    "logs_router",
    "realtime_router",
]

# Backward compatibility aliases
admin_env = env_router
admin_logs = logs_router
admin_realtime = realtime_router
