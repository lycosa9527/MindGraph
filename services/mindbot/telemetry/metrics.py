"""In-process MindBot callback counters by ``X-MindBot-Error-Code`` (thread-safe).

Each of the three accumulator dicts is capped at ``MINDBOT_METRICS_MAX_KEYS``
(default 10 000) using an LRU-style ``OrderedDict``; when inserting a new key
beyond the cap the oldest entry is evicted so memory is bounded.
"""

from __future__ import annotations

import collections
import functools
import logging
from threading import Lock
from typing import Any, Optional

from utils.env_helpers import env_int

logger = logging.getLogger(__name__)

_METRICS_MAX_KEYS_DEFAULT = 10_000


@functools.cache
def _metrics_max_keys() -> int:
    return max(100, env_int("MINDBOT_METRICS_MAX_KEYS", _METRICS_MAX_KEYS_DEFAULT))


def _bounded_incr(
    mapping: collections.OrderedDict,  # type: ignore[type-arg]
    key: Any,
    max_keys: int,
) -> None:
    """Increment mapping[key] with LRU eviction once len >= max_keys."""
    if key in mapping:
        mapping[key] += 1
        mapping.move_to_end(key)
    else:
        if len(mapping) >= max_keys:
            mapping.popitem(last=False)
        mapping[key] = 1


class MindbotMetrics:
    """Lightweight counters for DingTalk callback outcomes."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counts: collections.OrderedDict[str, int] = collections.OrderedDict()
        self._by_org: collections.OrderedDict[int, collections.OrderedDict[str, int]] = collections.OrderedDict()
        self._by_robot: collections.OrderedDict[str, collections.OrderedDict[str, int]] = collections.OrderedDict()

    def record_error_code(self, code: str) -> None:
        if not isinstance(code, str) or not code.strip():
            return
        with self._lock:
            _bounded_incr(self._counts, code.strip(), _metrics_max_keys())

    def record_from_headers(self, headers: dict[str, str]) -> None:
        raw = headers.get("X-MindBot-Error-Code")
        if raw is None:
            code_s = "MINDBOT_MISSING_CODE"
        else:
            stripped = raw.strip() if isinstance(raw, str) else ""
            code_s = stripped if stripped else "MINDBOT_MISSING_CODE"
        org_id: Optional[int] = None
        org_raw = headers.get("X-MindBot-Organization-Id")
        if org_raw is not None and str(org_raw).strip().isdigit():
            org_id = int(str(org_raw).strip())
        robot = headers.get("X-MindBot-Robot-Code")
        max_keys = _metrics_max_keys()
        with self._lock:
            _bounded_incr(self._counts, code_s, max_keys)
            if org_id is not None:
                if org_id not in self._by_org:
                    if len(self._by_org) >= max_keys:
                        self._by_org.popitem(last=False)
                    self._by_org[org_id] = collections.OrderedDict()
                else:
                    self._by_org.move_to_end(org_id)
                _bounded_incr(self._by_org[org_id], code_s, max_keys)
            if robot and isinstance(robot, str) and robot.strip():
                rc = robot.strip()
                if rc not in self._by_robot:
                    if len(self._by_robot) >= max_keys:
                        self._by_robot.popitem(last=False)
                    self._by_robot[rc] = collections.OrderedDict()
                else:
                    self._by_robot.move_to_end(rc)
                _bounded_incr(self._by_robot[rc], code_s, max_keys)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "by_error_code": dict(self._counts),
                "by_organization_id": {oid: dict(codes) for oid, codes in self._by_org.items()},
                "by_robot_code": {rk: dict(codes) for rk, codes in self._by_robot.items()},
            }


def mindbot_long_lived_maps_snapshot() -> dict[str, Any]:
    """
    In-process MindBot structures that can grow with org / credential cardinality.

    Intended for admin diagnostics and capacity planning (not high-cardinality series).
    """
    from services.mindbot.platforms.dingtalk.auth import oauth as oauth_mod
    from services.mindbot.platforms.dingtalk.cards.stream_client import get_stream_manager

    mgr = get_stream_manager()
    return {
        "oauth_lock_map_size": oauth_mod.oauth_lock_map_size(),
        "oauth_lock_map_max": oauth_mod.oauth_lock_map_max_configured(),
        "dingtalk_stream_registered_clients": mgr.registered_client_count(),
    }


mindbot_metrics = MindbotMetrics()
