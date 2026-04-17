"""
Per-process Redis circuit breaker (G8 from db-tuning audit).
============================================================

Why
---
``services/redis/redis_client.py`` and ``services/redis/redis_async_ops.py``
already retry transient ``redis.ConnectionError`` / ``redis.TimeoutError``
with bounded exponential backoff (3 attempts, max ~0.4 s).  That works
beautifully for blip-style outages but turns into a self-DoS when Redis is
genuinely down: every request pays the full retry budget before degrading,
multiplying tail latency by the worker count.

A circuit breaker fixes this with a tiny state machine:

* **CLOSED**   — normal operation, every call goes through.
* **OPEN**     — failure threshold tripped; calls short-circuit immediately
  with the caller-supplied default for ``cooldown_s`` seconds.
* **HALF_OPEN**— after the cooldown one probe call is allowed; success
  closes the breaker, failure re-opens it for another cooldown.

This matches the `Release It!` (Nygard) pattern and is the same shape used
inside high-traffic Python services (envoy, hystrix, pybreaker).  We keep
the implementation deliberately tiny so it can be reasoned about in one
screen.

Design choices
--------------
* Per-process state — every uvicorn worker tracks its own breaker so a
  single misbehaving worker does not stop the others from probing.  This
  is a Redis caching breaker, not a distributed one.
* Counts only *connection-class* failures (``ConnectionError`` /
  ``TimeoutError``).  Programming errors (``ResponseError``,
  ``DataError``) must still surface so they can be fixed.
* Disable-by-env (``REDIS_CIRCUIT_BREAKER=false``) so operators can flip
  it off during incidents without redeploying.
* Thread-safe via ``threading.Lock`` for the sync path; the async path
  reuses the same state because asyncio runs single-threaded inside each
  worker.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2026 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
import threading
import time
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class _State(str, Enum):
    """Three-state circuit breaker FSM."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


def _env_bool(name: str, default: bool) -> bool:
    """Parse a boolean env var with a sane default."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"false", "0", "no", "off", ""}


def _env_int(name: str, default: int) -> int:
    """Parse an integer env var, falling back on the default if unparseable."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default


def _env_float(name: str, default: float) -> float:
    """Parse a float env var, falling back on the default if unparseable."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (ValueError, TypeError):
        return default


class RedisCircuitBreaker:
    """Single-instance, thread-safe Redis circuit breaker.

    Attributes
    ----------
    failure_threshold:
        Consecutive connection-class failures that flip CLOSED → OPEN.
    cooldown_s:
        Seconds to remain OPEN before allowing a single probe (HALF_OPEN).
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_s: float = 10.0,
    ) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_s = max(0.1, cooldown_s)
        self._state: _State = _State.CLOSED
        self._consecutive_failures: int = 0
        self._opened_at: float = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API used by the retry decorators
    # ------------------------------------------------------------------
    @property
    def state(self) -> str:
        """Current breaker state — exposed for the health endpoint."""
        return self._state.value

    def allow_request(self) -> bool:
        """Return ``True`` if a real Redis call should be attempted now.

        * CLOSED      → always True.
        * OPEN        → True only once the cooldown elapses; transitions to
                        HALF_OPEN and lets the probe through.
        * HALF_OPEN   → False — only the probe acquired during the OPEN→
                        HALF_OPEN transition is allowed; everyone else
                        short-circuits while we wait for the probe verdict.
        """
        with self._lock:
            if self._state is _State.CLOSED:
                return True

            if self._state is _State.OPEN:
                if (time.monotonic() - self._opened_at) >= self.cooldown_s:
                    self._state = _State.HALF_OPEN
                    logger.info("[RedisBreaker] cooldown elapsed → HALF_OPEN (probe)")
                    return True
                return False

            # HALF_OPEN: probe is already in flight, nobody else may pass.
            return False

    def record_success(self) -> None:
        """Reset the failure counter and close the breaker if it was probing."""
        with self._lock:
            if self._consecutive_failures or self._state is not _State.CLOSED:
                self._consecutive_failures = 0
                if self._state is not _State.CLOSED:
                    logger.info("[RedisBreaker] probe succeeded → CLOSED")
                self._state = _State.CLOSED

    def record_failure(self) -> None:
        """Bump the failure counter and open the breaker once the threshold trips."""
        with self._lock:
            if self._state is _State.HALF_OPEN:
                self._state = _State.OPEN
                self._opened_at = time.monotonic()
                logger.warning(
                    "[RedisBreaker] probe failed → OPEN for %.1fs",
                    self.cooldown_s,
                )
                return

            self._consecutive_failures += 1
            if self._state is _State.CLOSED and self._consecutive_failures >= self.failure_threshold:
                self._state = _State.OPEN
                self._opened_at = time.monotonic()
                logger.warning(
                    "[RedisBreaker] %d consecutive failures → OPEN for %.1fs",
                    self._consecutive_failures,
                    self.cooldown_s,
                )

    def snapshot(self) -> dict:
        """Return a JSON-friendly view for /health and observability tooling."""
        with self._lock:
            remaining = 0.0
            if self._state is _State.OPEN:
                remaining = max(0.0, self.cooldown_s - (time.monotonic() - self._opened_at))
            return {
                "state": self._state.value,
                "consecutive_failures": self._consecutive_failures,
                "failure_threshold": self.failure_threshold,
                "cooldown_s": self.cooldown_s,
                "open_remaining_s": round(remaining, 2),
            }


# ----------------------------------------------------------------------
# Process-wide singleton
# ----------------------------------------------------------------------
_BREAKER_ENABLED = _env_bool("REDIS_CIRCUIT_BREAKER", True)
_BREAKER_FAILURE_THRESHOLD = _env_int("REDIS_CB_FAILURE_THRESHOLD", 5)
_BREAKER_COOLDOWN_S = _env_float("REDIS_CB_COOLDOWN_S", 10.0)

_BREAKER: Optional[RedisCircuitBreaker] = None
_BREAKER_INIT_LOCK = threading.Lock()


def get_breaker() -> RedisCircuitBreaker:
    """Lazy-init the per-process breaker singleton.

    Lazy because some test environments import this module before the
    ``REDIS_CIRCUIT_BREAKER_*`` env vars are set; the values are captured
    at first access.
    """
    global _BREAKER  # pylint: disable=global-statement
    if _BREAKER is not None:
        return _BREAKER
    with _BREAKER_INIT_LOCK:
        if _BREAKER is None:
            _BREAKER = RedisCircuitBreaker(
                failure_threshold=_BREAKER_FAILURE_THRESHOLD,
                cooldown_s=_BREAKER_COOLDOWN_S,
            )
    return _BREAKER


def is_breaker_enabled() -> bool:
    """Whether retry decorators should consult the breaker at all."""
    return _BREAKER_ENABLED


def breaker_snapshot() -> dict:
    """Public helper used by the health endpoint."""
    snap = get_breaker().snapshot()
    snap["enabled"] = _BREAKER_ENABLED
    return snap
