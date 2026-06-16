"""Minimal websocket-client stub for optional load-test harness typing."""

from typing import Any


class WebSocketException(Exception):
    """websocket-client exception stub."""


class WebSocket:
    """websocket-client WebSocket stub."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        _ = (args, kwargs)

    def connect(self, url: str, *args: Any, **kwargs: Any) -> None:
        _ = (url, args, kwargs)

    def send(self, payload: str) -> None:
        _ = payload

    def recv(self) -> str:
        return ""

    def close(self) -> None:
        return None


def create_connection(url: str, *args: Any, **kwargs: Any) -> WebSocket:
    """Create a WebSocket connection stub."""
    _ = (url, args, kwargs)
    return WebSocket()
