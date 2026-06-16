"""Kitty Agent router: realtime WebSocket and REST helpers."""

from __future__ import annotations

from routers.features.kitty import routes as kitty_routes
from routers.features.kitty.state import router

__all__ = ["router", "routes"]

routes = kitty_routes
