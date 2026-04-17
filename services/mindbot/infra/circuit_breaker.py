"""Hybrid in-memory + Redis circuit breaker for MindBot's Dify API calls.

Design
------
- CLOSED: normal operation; failures are counted.
- OPEN: failing-fast; new calls are rejected without reaching Dify.
- HALF-OPEN: one probe is allowed through after the reset window to test recovery.

Each key (typically org_id or a global key) gets its own :class:`CircuitBreaker`
instance held in a module-level dict.  Redis provides cross-worker consistency:
failure counts are tracked in Redis so all Uvicorn workers share the same
circuit state.  When Redis is unavailable, the in-memory breaker acts as a
per-process fallback.

Semantics alignment
-------------------
Both the Redis counter and the in-memory :class:`CircuitBreaker` use a
**fixed-window** model: the failure count is reset when the key expires after
``MINDBOT_CIRCUIT_BREAKER_RESET_SECONDS``.  Redis uses
``redis_incr_fixed_window`` (TTL set only on first increment) so the window
does not slide with activity.  In-memory uses consecutive failure counting with
an automatic reset after the same window — both open at ``threshold`` failures
within the window and half-open after the window elapses.

Probe-lock failure handling
---------------------------
When the Redis SETNX for the probe lock returns ``None`` (Redis error, not
"probe already taken"), the code falls through to the in-memory breaker rather
than fail-closing, so a Redis error during probe acquisition does not block
all traffic indefinitely.

Configuration (env vars)
------------------------
MINDBOT_CIRCUIT_BREAKER_ENABLED           default True
MINDBOT_CIRCUIT_BREAKER_FAILURE_THRESHOLD default 5  (failures within window to open)
MINDBOT_CIRCUIT_BREAKER_RESET_SECONDS    default 60  (window size / seconds before probe)
MINDBOT_CIRCUIT_BREAKER_MAX_KEYS         default 2000 (max in-memory breaker entries;
                                          oldest evicted when full)
"""

from __future__ import annotations

import collections
import functools
import logging
import time
from typing import Literal

from services.mindbot.infra.redis_async import (
    redis_delete,
    redis_get,
    redis_incr_fixed_window,
    redis_setnx_ttl,
)
from utils.env_helpers import env_bool, env_float, env_int

logger = logging.getLogger(__name__)

_breakers: collections.OrderedDict[str, "CircuitBreaker"] = collections.OrderedDict()

_CB_REDIS_KEY_PREFIX = "mindbot:cb:"


@functools.cache
def _cb_max_keys() -> int:
    return max(100, env_int("MINDBOT_CIRCUIT_BREAKER_MAX_KEYS", 2000))


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
    In-memory circuit breaker for a single resource key (per-process fallback).

    ``asyncio`` is single-threaded, so attribute reads/writes are atomic enough
    for our use case (no GIL concerns for coroutine-switching tasks).

    State transitions are driven by :meth:`state`, which is the single source of
    truth.  ``is_open`` and ``is_half_open`` are thin wrappers so callers are not
    sensitive to call order.
    """

    def __init__(self) -> None:
        self._failures: int = 0
        self._opened_at: float = 0.0
        self._is_open: bool = False

    def state(self) -> Literal["closed", "open", "half_open"]:
        """Return the current circuit state without side effects."""
        if not self._is_open:
            return "closed"
        if time.monotonic() - self._opened_at >= _cb_reset_seconds():
            return "half_open"
        return "open"

    def is_open(self) -> bool:
        return self.state() == "open"

    def is_half_open(self) -> bool:
        return self.state() == "half_open"

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
    if key in _breakers:
        _breakers.move_to_end(key)
        return _breakers[key]
    max_keys = _cb_max_keys()
    if len(_breakers) >= max_keys:
        evicted_key, _ = _breakers.popitem(last=False)
        logger.warning(
            "[MindBot] circuit_breaker_evicted key=%s (max_keys=%s reached)",
            evicted_key,
            max_keys,
        )
    _breakers[key] = CircuitBreaker()
    return _breakers[key]


async def check_circuit_breaker(key: str) -> bool:
    """
    Return True if the call should proceed, False if the circuit is open.

    Checks Redis failure count first for cross-worker consistency; falls back
    to the in-memory breaker when Redis is unavailable.

    In half-open state a Redis SETNX lock ensures only one probe request is
    allowed across all workers, preventing thundering-herd recovery.
    """
    if not _cb_enabled():
        return True

    threshold = _cb_failure_threshold()
    redis_key = f"{_CB_REDIS_KEY_PREFIX}{key}"
    redis_count = await redis_get(redis_key)
    if redis_count is not None:
        try:
            count = int(redis_count)
        except (ValueError, TypeError):
            count = 0
        if count >= threshold:
            probe_lock_key = f"{_CB_REDIS_KEY_PREFIX}probe:{key}"
            reset_s = int(_cb_reset_seconds())
            probe_won = await redis_setnx_ttl(probe_lock_key, "1", reset_s)
            if probe_won is True:
                logger.info(
                    "[MindBot] circuit_breaker_half_open key=%s allowing_single_probe",
                    key,
                )
                return True
            if probe_won is False:
                # Another worker already holds the probe lock; reject this request.
                logger.warning(
                    "[MindBot] circuit_breaker_rejected key=%s redis_count=%s",
                    key,
                    count,
                )
                return False
            # probe_won is None: Redis error during SETNX. Fall through to the
            # in-memory breaker so a Redis failure does not block all traffic.
            logger.warning(
                "[MindBot] circuit_breaker_probe_redis_error key=%s falling_back_to_in_memory",
                key,
            )

    breaker = get_breaker(key)
    breaker_state = breaker.state()
    if breaker_state == "half_open":
        logger.info("[MindBot] circuit_breaker_half_open key=%s allowing_probe", key)
        return True
    if breaker_state == "open":
        logger.warning("[MindBot] circuit_breaker_rejected key=%s", key)
        return False
    return True


async def record_dify_success(key: str) -> None:
    """Record a successful Dify call and close the circuit if open."""
    if not _cb_enabled():
        return
    get_breaker(key).record_success()
    await redis_delete(f"{_CB_REDIS_KEY_PREFIX}{key}")
    await redis_delete(f"{_CB_REDIS_KEY_PREFIX}probe:{key}")


async def record_dify_failure(key: str) -> None:
    """Record a Dify failure; open the circuit after threshold failures within the window.

    Uses ``redis_incr_fixed_window`` so the failure count is bounded to the reset
    window and does not extend indefinitely with activity (matching the in-memory
    breaker's time-based reset behaviour).
    """
    if not _cb_enabled():
        return
    get_breaker(key).record_failure(key)
    ttl = int(_cb_reset_seconds())
    await redis_incr_fixed_window(f"{_CB_REDIS_KEY_PREFIX}{key}", ttl)
