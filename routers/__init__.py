"""
MindGraph FastAPI Routers
==========================

This package contains all FastAPI route modules organized by functionality.

Routers:
- api/: Main API endpoints package (diagrams, LLM, agents) - refactored into modular structure
- pages.py: Template rendering routes (HTML pages)
- auth.py: Authentication endpoints
- admin_env.py: Admin environment settings
- admin_logs.py: Admin log streaming
- node_palette.py: Node Palette endpoints
- features/kitty/: Kitty Agent (realtime WS + REST helpers)
- update_notification.py: Update notification system

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from . import api, auth, inline_recommendations, node_palette, public_dashboard, relationship_labels
from .admin import env_router as admin_env
from .admin import logs_router as admin_logs
from .admin import realtime_router as admin_realtime
from .core import pages, update_notification, vue_spa
from .features import askonce, debateverse, gewe, kitty, library

__all__ = [
    "api",
    "pages",
    "auth",
    "admin_env",
    "admin_logs",
    "admin_realtime",
    "node_palette",
    "relationship_labels",
    "inline_recommendations",
    "kitty",
    "update_notification",
    "public_dashboard",
    "askonce",
    "debateverse",
    "library",
    "gewe",
    "vue_spa",
]
