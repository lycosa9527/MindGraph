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
from . import pages
from . import cache
from . import auth
from . import admin_env
from . import admin_logs
from . import admin_realtime
from . import node_palette
from . import voice
from . import update_notification
from . import tab_mode
from . import public_dashboard
from . import school_zone
from . import askonce
from . import debateverse
from . import vue_spa

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
    "vue_spa"
]

