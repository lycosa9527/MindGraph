"""
MindGraph FastAPI Routers
==========================

This package contains all FastAPI route modules organized by functionality.

Routers:
- api/: Main API endpoints package (diagrams, LLM, agents) - refactored into modular structure
- pages.py: Template rendering routes (HTML pages)
- cache.py: JavaScript cache status endpoints
- auth.py: Authentication endpoints
- admin_env.py: Admin environment settings
- admin_logs.py: Admin log streaming
- node_palette.py: Node Palette endpoints
- voice.py: VoiceAgent endpoints
- update_notification.py: Update notification system

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from . import api
from . import auth
from . import node_palette
from . import public_dashboard
from .admin import env_router as admin_env, logs_router as admin_logs, realtime_router as admin_realtime
from .features import voice, tab_mode, school_zone, askonce, debateverse, library, gewe
from .core import pages, cache, vue_spa, update_notification

__all__ = [
    "api",
    "pages",
    "cache",
    "auth",
    "admin_env",
    "admin_logs",
    "admin_realtime",
    "node_palette",
    "voice",
    "update_notification",
    "tab_mode",
    "public_dashboard",
    "school_zone",
    "askonce",
    "debateverse",
    "library",
    "gewe",
    "vue_spa"
]
