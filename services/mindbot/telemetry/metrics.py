"""In-process MindBot callback counters by ``X-MindBot-Error-Code`` (thread-safe)."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock
from typing import Any, Optional

from services.mindbot.errors import MindbotErrorCode


class MindbotMetrics:
    """Lightweight counters for DingTalk callback outcomes."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counts: dict[str, int] = defaultdict(int)
        self._by_org: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._by_robot: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def record_error_code(self, code: str) -> None:
        if not isinstance(code, str) or not code.strip():
            return
        with self._lock:
            self._counts[code.strip()] += 1

    def record_from_headers(self, headers: dict[str, str]) -> None:
        raw = headers.get("X-MindBot-Error-Code", MindbotErrorCode.OK.value)
        code_s = raw.strip() if isinstance(raw, str) else MindbotErrorCode.OK.value
        org_id: Optional[int] = None
        org_raw = headers.get("X-MindBot-Organization-Id")
        if org_raw is not None and str(org_raw).strip().isdigit():
            org_id = int(str(org_raw).strip())
        robot = headers.get("X-MindBot-Robot-Code")
        with self._lock:
            self._counts[code_s] += 1
            if org_id is not None:
                self._by_org[org_id][code_s] += 1
            if robot and isinstance(robot, str) and robot.strip():
                rc = robot.strip()
                self._by_robot[rc][code_s] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "by_error_code": dict(self._counts),
                "by_organization_id": {
                    oid: dict(codes) for oid, codes in self._by_org.items()
                },
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
