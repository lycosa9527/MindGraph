"""Environment configuration for per-user daily LLM token cap."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_USER_DAILY_TOKEN_CAP = 5_000_000


def daily_token_cap() -> int:
    """Configured daily cap; 0 disables enforcement."""
    raw = os.getenv("USER_DAILY_TOKEN_CAP", str(DEFAULT_USER_DAILY_TOKEN_CAP))
    try:
        return max(0, int(raw))
    except ValueError:
        logger.warning("[UserDailyToken] Invalid USER_DAILY_TOKEN_CAP=%r; using default", raw)
        return DEFAULT_USER_DAILY_TOKEN_CAP
