"""
Admin Routers

Admin-related endpoints for environment settings, logs, realtime monitoring,
and database management.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from .cos import router as cos_router
from .database import router as database_router
from .env import router as env_router
from .logs import router as logs_router
from .realtime import router as realtime_router

__all__ = [
    "cos_router",
    "database_router",
    "env_router",
    "logs_router",
    "realtime_router",
]

# Backward compatibility aliases
admin_env = env_router
admin_logs = logs_router
admin_realtime = realtime_router
admin_database = database_router
