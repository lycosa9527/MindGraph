"""
Shared RLS mode constants (import leaf for cycle breaking).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations


MODE_AUTHENTICATED = "authenticated"
MODE_PANEL = "panel"
MODE_PANEL_SUPERADMIN = "panel_superadmin"
MODE_PUBLIC = "public"
MODE_DASHBOARD = "dashboard"
MODE_MINDBOT_SERVICE = "mindbot_service"
MODE_DENY = "deny"
MODE_SYSTEM = "system"


class RlsListenerRegistration:
    """One-shot guard for SQLAlchemy after_begin listener registration."""

    registered = False
