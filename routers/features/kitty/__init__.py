"""Kitty Agent router: realtime WebSocket and REST helpers."""

from __future__ import annotations

from typing import Any

from routers.features.kitty.state import router

__all__ = ["router", "routes"]


def __getattr__(name: str) -> Any:
    """Load ``routes`` lazily so importing helpers does not pull ``kitty_routes`` first."""
    if name == "routes":
        import routers.features.kitty.routes as routes_module

        return routes_module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
