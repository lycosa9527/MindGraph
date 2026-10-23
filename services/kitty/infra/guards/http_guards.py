"""Kitty HTTP feature gates and shared REST response bodies.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict

from models.domain.auth import User

KITTY_MOBILE_BOOTSTRAP_DISABLED_BODY: Dict[str, Any] = {
    "recommended_scope": None,
    "desktop_focus": {
        "diagram_library_id": None,
        "updated_at": None,
        "canvas_owner_present": False,
    },
    "context": {
        "diagram_data": {},
        "selected_nodes": [],
        "diagram_type": "circle_map",
    },
    "diagram_type": "circle_map",
    "active_panel": "none",
    "source": "empty",
}


async def kitty_http_allowed(current_user: User) -> bool:
    """Kitty Agent is available to every signed-in user."""
    return isinstance(current_user, User)
