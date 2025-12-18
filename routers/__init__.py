"""
MindGraph FastAPI Routers
==========================

This package contains all FastAPI route modules organized by functionality.

Routers:
- api.py: Main API endpoints (diagrams, LLM, agents)
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
"""

__all__ = [
    "api",
    "pages",
    "cache",
    "auth",
    "admin_env",
    "admin_logs",
    "node_palette",
    "voice",
    "update_notification"
]

