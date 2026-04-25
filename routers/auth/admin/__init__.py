"""
Admin Router Aggregation
========================

Aggregates all admin sub-routers into a single router for easy inclusion in the main app.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from fastapi import APIRouter

from . import (
    organizations,
    roles,
    users,
    school_users,
    settings,
    stats,
    stats_trends,
    performance,
    api_keys,
    bayi,
    teacher_usage,
    feature_org_access,
    geolite,
)

# Create admin router aggregation
admin_router = APIRouter()

# Include all admin sub-routers
admin_router.include_router(organizations.router)
admin_router.include_router(roles.router)
admin_router.include_router(users.router)
admin_router.include_router(school_users.router)
admin_router.include_router(settings.router)
admin_router.include_router(stats.router)
admin_router.include_router(stats_trends.router)
admin_router.include_router(performance.router)
admin_router.include_router(api_keys.router)
admin_router.include_router(bayi.router)
admin_router.include_router(teacher_usage.router)
admin_router.include_router(feature_org_access.router)
admin_router.include_router(geolite.router)

__all__ = ["admin_router"]
