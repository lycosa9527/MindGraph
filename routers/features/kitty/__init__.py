"""
Kitty Agent router: realtime WebSocket and REST helpers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from routers.features.kitty import routes as kitty_routes
from routers.features.kitty.state import router

__all__ = ["router", "routes"]

routes = kitty_routes
