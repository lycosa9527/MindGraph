"""
Admin Router Aggregation
========================

Aggregates all admin sub-routers into a single router for easy inclusion in the main app.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from fastapi import APIRouter

from . import organizations, users, settings, stats, stats_trends, api_keys, bayi, teacher_usage

# Create admin router aggregation
admin_router = APIRouter()

# Include all admin sub-routers
admin_router.include_router(organizations.router)
admin_router.include_router(users.router)
admin_router.include_router(settings.router)
admin_router.include_router(stats.router)
admin_router.include_router(stats_trends.router)
admin_router.include_router(api_keys.router)
admin_router.include_router(bayi.router)
admin_router.include_router(teacher_usage.router)

__all__ = ['admin_router']



