"""
WebSocket inbound limits (frame size, per-connection message rate).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os
import time
from collections import deque
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

from starlette.websockets import WebSocketDisconnect


def _optional_positive_int(name: str) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return 0
    try:
        parsed = int(raw)
    except ValueError:
        return 0
    return parsed if parsed > 0 else 0


# Max UTF-8 byte length for a single inbound text frame (non-collab endpoints).
DEFAULT_MAX_WS_TEXT_BYTES = 256 * 1024

# Collab full-spec updates may reach ~768 KiB JSON; cap inbound at 1 MiB UTF-8.
WORKSHOP_WS_BYTES_ENV = _optional_positive_int("COLLAB_WS_MAX_TEXT_BYTES")
if WORKSHOP_WS_BYTES_ENV:
    WORKSHOP_MAX_WS_TEXT_BYTES = min(max(WORKSHOP_WS_BYTES_ENV, 65536), 2 * 1024 * 1024)
else:
    WORKSHOP_MAX_WS_TEXT_BYTES = 1024 * 1024

# Maximum dict/list nesting for inbound collab JSON (DoS guard).
COLLAB_JSON_DEPTH_ENV = _optional_positive_int("COLLAB_WS_MAX_JSON_DEPTH")
if COLLAB_JSON_DEPTH_ENV:
    MAX_COLLAB_INBOUND_JSON_DEPTH = max(8, min(COLLAB_JSON_DEPTH_ENV, 128))
else:
    MAX_COLLAB_INBOUND_JSON_DEPTH = 48

# Sliding window: max JSON control/data messages per second per connection.
DEFAULT_MAX_WS_MESSAGES_PER_SECOND = 40


def text_payload_from_websocket_receive(message: Mapping[str, object]) -> str:
    """
    Decode user payload from an ASGI ``websocket.receive`` event.

    Text frames expose ``text``; binary frames expose ``bytes``. Starlette's
    ``receive_text()`` raises KeyError if the client sends a binary frame.
    """
    val = message.get("text")
    if val is not None:
        return str(val)
    raw = message.get("bytes")
    if raw is not None:
        return raw.decode("utf-8", errors="replace")
    return ""


async def safe_websocket_send_text(websocket: WebSocket, text: str) -> None:
    """Send a text frame; ignore failures when the client has already gone away."""
    try:
        await websocket.send_text(text)
    except (RuntimeError, ConnectionError, OSError, WebSocketDisconnect):
        pass


async def receive_websocket_text_frame(websocket: WebSocket) -> str:
    """Next client data frame as UTF-8 text, or raise WebSocketDisconnect."""
    message = await websocket.receive()
    if message["type"] == "websocket.disconnect":
        raw_code = message.get("code", 1000)
        if raw_code is None:
            code = 1000
        else:
            try:
                code = int(raw_code)
            except (TypeError, ValueError):
                code = 1000
        raise WebSocketDisconnect(code, message.get("reason"))
    return text_payload_from_websocket_receive(message)


def inbound_text_exceeds_limit(text: str, max_bytes: int) -> bool:
    """Return True if *text* encodes to more than *max_bytes* UTF-8 bytes."""
    return len(text.encode("utf-8")) > max_bytes


def json_value_nesting_depth(value: Any, current: int = 0) -> int:
    """Return maximum nested dict/list depth (0 for scalars)."""
    if isinstance(value, dict):
        if not value:
            return current + 1
        return max(json_value_nesting_depth(item, current + 1) for item in value.values())
    if isinstance(value, list):
        if not value:
            return current + 1
        return max(json_value_nesting_depth(item, current + 1) for item in value)
    return current


def collab_json_exceeds_depth(value: Any, max_depth: int) -> bool:
    """True if *value* nests deeper than *max_depth*."""
    return json_value_nesting_depth(value) > max_depth


class WebsocketMessageRateLimiter:
    """Sliding 1-second window limiter for WebSocket message frequency."""

    def __init__(self, max_messages_per_second: int) -> None:
        self._max = max_messages_per_second
        self._timestamps: deque[float] = deque()

    def allow(self) -> bool:
        """Return True if another message is allowed in the current window."""
        now = time.monotonic()
        while self._timestamps and now - self._timestamps[0] > 1.0:
            self._timestamps.popleft()
        if len(self._timestamps) >= self._max:
            return False
        self._timestamps.append(now)
        return True
