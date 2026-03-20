"""
WebSocket inbound limits (frame size, per-connection message rate).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import time
from collections import deque


# Max UTF-8 byte length for a single inbound text frame (abuse / DoS bound).
DEFAULT_MAX_WS_TEXT_BYTES = 256 * 1024

# Sliding window: max JSON control/data messages per second per connection.
DEFAULT_MAX_WS_MESSAGES_PER_SECOND = 40


def inbound_text_exceeds_limit(text: str, max_bytes: int) -> bool:
    """Return True if *text* encodes to more than *max_bytes* UTF-8 bytes."""
    return len(text.encode("utf-8")) > max_bytes


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
