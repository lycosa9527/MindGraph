"""DingTalk ``PUT /v1.0/card/streaming`` QPS shaping and throttle detection.

DingTalk enforces per-app-key per-API QPS (often around 20/s for streaming update).
Pressure tests trigger ``HTTP 403`` with ``Forbidden.AccessDenied.QpsLimitForAppkeyAndApi``.
Official mitigation: sleep ~1s and retry; proactively limit call rate (queue / rate limiter).

This module provides:
- A per-``clientId`` async sliding-window limiter using a FIFO waiter queue so only
  one coroutine wakes per freed slot (O(1) contention rather than O(N) spin-sleep).
  Single-process only; for multiple hosts use an external distributed limiter or lower
  ``MINDBOT_DINGTALK_STREAMING_QPS_PER_APP`` per instance so the **sum across all
  workers** stays under DingTalk's ~20/s cap for that app key.
  Example: 2 workers → set the env var to 9 per instance (9+9=18 < 20).
- Helpers to recognise QPS error bodies so callers can sleep and retry.

Multi-worker guidance (DingTalk "分布式限流"):
  DingTalk's 20/s limit is per application (appkey) per API, shared across all
  processes hitting the same DingTalk app.  Options:
    1. Lower env var per instance: MINDBOT_DINGTALK_STREAMING_QPS_PER_APP = floor(18 / N)
    2. Add a Redis INCR+EXPIRE second-bucket counter keyed by client_id to replace or
       complement this in-process limiter (requires Redis available in all workers).
  Restart is required to apply changes to MINDBOT_DINGTALK_STREAMING_QPS_PER_APP or
  MINDBOT_DINGTALK_STREAMING_QPS_WINDOW_MS — values are read once at first limiter
  creation and cached; a warning is logged if a later call supplies different values.
"""

from __future__ import annotations

import asyncio
import collections
import logging
from typing import Any, Optional

from utils.env_helpers import env_int

logger = logging.getLogger(__name__)

# New OpenAPI (from DingTalk JSON ``code`` field).
_QPS_LIMIT_APP_AND_API = "Forbidden.AccessDenied.QpsLimitForAppkeyAndApi"
_QPS_LIMIT_API_GLOBAL = "Forbidden.AccessDenied.QpsLimitForApi"

_limiters_guard = asyncio.Lock()
_limiters: collections.OrderedDict[str, _AsyncSlidingWindowLimiter] = (
    collections.OrderedDict()
)

_MINDBOT_QPS_LIMITER_MAX_KEYS_DEFAULT = 500


def _qps_limiter_max_keys() -> int:
    return max(10, env_int("MINDBOT_QPS_LIMITER_MAX_KEYS", _MINDBOT_QPS_LIMITER_MAX_KEYS_DEFAULT))


class _AsyncSlidingWindowLimiter:
    """At most ``max_calls`` acquisitions per ``window_seconds`` (monotonic clock).

    Uses a per-waiter FIFO ``asyncio.Event`` queue so that when a slot becomes
    available only the **first** queued coroutine is woken (O(1) per slot, not O(N)).
    Slot expiry is signalled via ``loop.call_later`` so no background task is needed.
    """

    def __init__(self, max_calls: int, window_seconds: float) -> None:
        self._max_calls = max(1, max_calls)
        self._window = max(0.001, window_seconds)
        self._lock = asyncio.Lock()
        self._times: list[float] = []
        self._waiters: collections.deque[asyncio.Event] = collections.deque()

    def _wake_next(self) -> None:
        """Signal the first queued waiter; invoked from ``loop.call_later``."""
        if self._waiters:
            self._waiters[0].set()

    async def acquire(self) -> None:
        loop = asyncio.get_running_loop()
        event: Optional[asyncio.Event] = None

        while True:
            async with self._lock:
                now = loop.time()
                self._times = [t for t in self._times if t > now - self._window]
                is_first = (
                    event is not None
                    and bool(self._waiters)
                    and self._waiters[0] is event
                )
                # Proceed when capacity is available and we are either not queued
                # (first arrival, no competition) or we are first in the waiter queue.
                if len(self._times) < self._max_calls and (not self._waiters or is_first):
                    if is_first:
                        self._waiters.popleft()
                    self._times.append(now)
                    # When the oldest slot expires, wake the next waiter (if any).
                    if self._waiters and self._times:
                        delay = self._times[0] + self._window - now
                        loop.call_later(max(delay, 0.001), self._wake_next)
                    return
                # First time we can't proceed: create an event and join the queue.
                if event is None:
                    event = asyncio.Event()
                    self._waiters.append(event)
                    # Schedule a wakeup for when the next slot becomes available.
                    if self._times:
                        delay = self._times[0] + self._window - now
                        loop.call_later(max(delay, 0.001), self._wake_next)
            # Wait for the wakeup signal, then re-check under the lock.
            await event.wait()
            event.clear()


def dingtalk_streaming_body_is_qps_throttle(body: Optional[dict[str, Any]]) -> bool:
    """
    Return True when DingTalk indicates QPS / rate limiting (retry after ~1s).

    Handles new API ``code`` strings and legacy numeric codes in ``code`` / ``message``.
    """
    if not body:
        return False
    code = str(body.get("code") or "").strip()
    msg = str(body.get("message") or body.get("msg") or "").strip()
    if code in (_QPS_LIMIT_APP_AND_API, _QPS_LIMIT_API_GLOBAL):
        return True
    if code in ("90018", "90002"):
        return True
    combined = f"{code} {msg}"
    if "90018" in combined or "90002" in combined:
        return True
    compact = combined.lower().replace(".", "")
    if "qpslimit" in compact:
        return True
    return False


def _effective_qps_per_worker() -> int:
    """Compute the per-worker QPS limit taking ``MINDBOT_DINGTALK_STREAMING_QPS_NUM_WORKERS`` into account.

    When deploying N Uvicorn workers that share the same DingTalk app key, set
    ``MINDBOT_DINGTALK_STREAMING_QPS_NUM_WORKERS=N`` and keep
    ``MINDBOT_DINGTALK_STREAMING_QPS_PER_APP`` at the absolute per-app cap (default
    18).  This function divides the cap by N so the **sum** across all workers stays
    under DingTalk's ~20/s limit.

    Example: 3 workers → MINDBOT_DINGTALK_STREAMING_QPS_NUM_WORKERS=3 → 18/3 = 6/s/worker.
    """
    total_cap = max(1, env_int("MINDBOT_DINGTALK_STREAMING_QPS_PER_APP", 18))
    num_workers = max(1, env_int("MINDBOT_DINGTALK_STREAMING_QPS_NUM_WORKERS", 1))
    if num_workers > 1:
        per_worker = max(1, total_cap // num_workers)
        logger.debug(
            "[MindBot] dingtalk_streaming_qps per_worker=%s total_cap=%s num_workers=%s",
            per_worker,
            total_cap,
            num_workers,
        )
        return per_worker
    return total_cap


async def acquire_dingtalk_streaming_qps_slot(app_key: str) -> None:
    """
    Block until a call to DingTalk card streaming/receiver APIs is allowed for this app key.

    Bound is ``MINDBOT_DINGTALK_STREAMING_QPS_PER_APP`` (default 18) per rolling second
    per process, under DingTalk's typical ~20/s per-app per-API cap.

    For multi-worker deployments set ``MINDBOT_DINGTALK_STREAMING_QPS_NUM_WORKERS`` to
    the number of Uvicorn workers so the effective per-worker limit is automatically
    computed as ``floor(MINDBOT_DINGTALK_STREAMING_QPS_PER_APP / NUM_WORKERS)``.

    Configuration is read **once** at limiter creation; changing the env vars at runtime
    has no effect until the process restarts.  A WARNING is logged if the env values
    differ from those used at creation (e.g. after a config hot-reload).
    """
    key = (app_key or "").strip() or "__missing_client_id__"
    max_calls = _effective_qps_per_worker()
    window_ms = env_int("MINDBOT_DINGTALK_STREAMING_QPS_WINDOW_MS", 1000)
    window_s = max(0.001, window_ms / 1000.0)
    async with _limiters_guard:
        if key not in _limiters:
            max_keys = _qps_limiter_max_keys()
            if len(_limiters) >= max_keys:
                evicted_key, _ = _limiters.popitem(last=False)
                logger.warning(
                    "[MindBot] dingtalk_qps_limiter_evicted app_key_tail=%s "
                    "(max_keys=%s reached)",
                    evicted_key[-6:] if len(evicted_key) > 6 else evicted_key,
                    max_keys,
                )
            _limiters[key] = _AsyncSlidingWindowLimiter(max_calls, window_s)
            _limiters[key]._cfg_max_calls = max_calls  # type: ignore[attr-defined]
            _limiters[key]._cfg_window_ms = window_ms  # type: ignore[attr-defined]
            logger.debug(
                "[MindBot] dingtalk_streaming_qps_limiter_created app_key_tail=%s max=%s window_ms=%s",
                key[-6:] if len(key) > 6 else key,
                max_calls,
                window_ms,
            )
        else:
            _limiters.move_to_end(key)
            stored = _limiters[key]
            prev_max = getattr(stored, "_cfg_max_calls", None)
            prev_ms = getattr(stored, "_cfg_window_ms", None)
            if prev_max is not None and prev_ms is not None:
                if prev_max != max_calls or prev_ms != window_ms:
                    logger.warning(
                        "[MindBot] dingtalk_streaming_qps_limiter_config_mismatch "
                        "app_key_tail=%s created_with max=%s window_ms=%s "
                        "current_env max=%s window_ms=%s — restart required to apply change",
                        key[-6:] if len(key) > 6 else key,
                        prev_max,
                        prev_ms,
                        max_calls,
                        window_ms,
                    )
    await _limiters[key].acquire()
