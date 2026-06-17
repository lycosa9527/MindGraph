"""Process-wide application runtime markers (uptime, etc.)."""

from __future__ import annotations

import time


class _AppRuntime:
    """Holder for values set during lifespan startup."""

    start_time: float | None = None


def set_app_start_time(start_time: float) -> None:
    """Record monotonic wall time when the application finished startup."""
    _AppRuntime.start_time = start_time


def get_uptime_seconds() -> float:
    """Seconds since startup, or 0 when startup has not completed."""
    if _AppRuntime.start_time is None:
        return 0.0
    return time.time() - _AppRuntime.start_time
