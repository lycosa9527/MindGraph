"""
Batch MindMate seminar answer pieces so the room is not painted on every token.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import time
from typing import Callable, Optional


class SeminarStreamCoalescer:
    """Hold answer text and release a delta often enough to look like typing.

    The first piece is released immediately. Later pieces wait for the interval
    or a size cap. ``interval_seconds`` of 0 releases every piece at once.
    """

    def __init__(
        self,
        *,
        interval_seconds: float,
        max_held_chars: int,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self._interval_seconds = interval_seconds
        self._max_held_chars = max_held_chars
        self._clock = clock if clock is not None else time.monotonic
        self._held: list[str] = []
        self._last_emit_at: Optional[float] = None

    def push(self, text: str) -> Optional[str]:
        """Add one upstream piece. Return a delta when the room should paint."""
        if not text:
            return None
        if self._interval_seconds <= 0:
            return text
        if self._last_emit_at is None:
            self._last_emit_at = self._clock()
            return text
        self._held.append(text)
        elapsed = self._clock() - self._last_emit_at
        held = "".join(self._held)
        if elapsed < self._interval_seconds and len(held) < self._max_held_chars:
            return None
        return self._take_held()

    def flush(self) -> Optional[str]:
        """Return any text still held, including a short tail at the end of a reply."""
        return self._take_held()

    def _take_held(self) -> Optional[str]:
        if not self._held:
            return None
        text = "".join(self._held)
        self._held.clear()
        self._last_emit_at = self._clock()
        return text
