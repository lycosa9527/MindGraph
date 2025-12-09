"""
MindGraph FastAPI Routers
==========================

This package contains all FastAPI route modules organized by functionality.

Routers:
- api.py: Main API endpoints (diagrams, LLM, agents)
- pages.py: Template rendering routes (HTML pages)
- learning.py: Learning mode endpoints (LangChain-powered)
- cache.py: JavaScript cache status endpoints
- auth.py: Authentication endpoints
- admin_env.py: Admin environment settings
- admin_logs.py: Admin log streaming
- thinking.py: ThinkGuide mode endpoints
- voice.py: VoiceAgent endpoints
- update_notification.py: Update notification system

Author: lycosa9527
Made by: MindSpring Team
"""

__all__ = [
    "api",
    "pages",
    "learning",
    "cache",
    "auth",
    "admin_env",
    "admin_logs",
    "thinking",
    "voice",
    "update_notification"
]

