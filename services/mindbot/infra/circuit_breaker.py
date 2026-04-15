"""Simple in-memory circuit breaker for MindBot's Dify API calls.

Design
------
- CLOSED: normal operation; failures are counted.
- OPEN: failing-fast; new calls are rejected without reaching Dify.
- HALF-OPEN: one probe is allowed through after the reset window to test recovery.

Each key (typically org_id or a global key) gets its own :class:`CircuitBreaker`
instance. The instances are held in a module-level dict keyed by the same string.

Configuration (env vars)
------------------------
MINDBOT_CIRCUIT_BREAKER_ENABLED           default True
MINDBOT_CIRCUIT_BREAKER_FAILURE_THRESHOLD default 5  (consecutive failures to open)
MINDBOT_CIRCUIT_BREAKER_RESET_SECONDS    default 60  (seconds before half-open probe)
"""

from __future__ import annotations

import functools
import logging
import time

from utils.env_helpers import env_bool, env_float, env_int

logger = logging.getLogger(__name__)

_breakers: dict[str, "CircuitBreaker"] = {}


@functools.cache
def _cb_enabled() -> bool:
    return env_bool("MINDBOT_CIRCUIT_BREAKER_ENABLED", True)


@functools.cache
def _cb_failure_threshold() -> int:
    return max(1, env_int("MINDBOT_CIRCUIT_BREAKER_FAILURE_THRESHOLD", 5))


@functools.cache
def _cb_reset_seconds() -> float:
    return max(5.0, env_float("MINDBOT_CIRCUIT_BREAKER_RESET_SECONDS", 60.0))


class CircuitBreaker:
    """
    Thread-safe (asyncio-safe) circuit breaker for a single resource key.

    ``asyncio`` is single-threaded, so attribute reads/writes are atomic enough
    for our use case (no GIL concerns for coroutine-switching tasks).
    """

    def __init__(self) -> None:
        self._failures: int = 0
        self._opened_at: float = 0.0
        self._is_open: bool = False

    def is_open(self) -> bool:
        """Return True if calls should be rejected right now."""
        if not self._is_open:
            return False
        elapsed = time.monotonic() - self._opened_at
        if elapsed >= _cb_reset_seconds():
            self._is_open = False
            return False
        return True

    def is_half_open(self) -> bool:
        """True when the reset window has elapsed — one probe should be allowed."""
        if not self._is_open:
            return False
        return time.monotonic() - self._opened_at >= _cb_reset_seconds()

    def record_success(self) -> None:
        self._failures = 0
        self._is_open = False

    def record_failure(self, key: str) -> None:
        self._failures += 1
        if self._failures >= _cb_failure_threshold():
            if not self._is_open:
                logger.warning(
                    "[MindBot] circuit_breaker_open key=%s failures=%s",
                    key,
                    self._failures,
                )
            self._is_open = True
            self._opened_at = time.monotonic()


def get_breaker(key: str) -> CircuitBreaker:
    if key not in _breakers:
        _breakers[key] = CircuitBreaker()
    return _breakers[key]


def check_circuit_breaker(key: str) -> bool:
    """
    Return True if the call should proceed, False if the circuit is open.

    Pass the org_id or a global string (e.g. ``"global"``) as ``key``.
    When the circuit breaker is disabled globally, always returns True.
    """
    if not _cb_enabled():
        return True
    breaker = get_breaker(key)
    if breaker.is_half_open():
        logger.info("[MindBot] circuit_breaker_half_open key=%s allowing_probe", key)
        return True
    if breaker.is_open():
        logger.warning("[MindBot] circuit_breaker_rejected key=%s", key)
        return False
    return True


def record_dify_success(key: str) -> None:
    """Record a successful Dify call and close the circuit if open."""
    if not _cb_enabled():
        return
    get_breaker(key).record_success()


def record_dify_failure(key: str) -> None:
    """Record a Dify failure; open the circuit after threshold consecutive failures."""
    if not _cb_enabled():
        return
    get_breaker(key).record_failure(key)
