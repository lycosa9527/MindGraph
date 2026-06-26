"""
Admin-readable log messages for Dify dual-server health checks and failover.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional, cast

from models.domain.auth import Organization
from services.redis.cache.redis_dify_server_health_cache import (
    DifyServerHealth,
    HEALTH_FAILURE_THRESHOLD,
)

LOG_PREFIX = "[Dify Failover]"


def org_label(org: Organization) -> str:
    """Return a school label that admins can recognize in log lines."""
    display = (cast(Optional[str], getattr(org, "display_name", None)) or "").strip()
    name = (cast(Optional[str], getattr(org, "name", None)) or "").strip()
    school_name = display or name
    if school_name:
        return f'"{school_name}" (org {org.id})'
    return f"org {org.id}"


def server_label(server: int, role: str) -> str:
    """Map internal role names to admin-facing server labels."""
    if role == "primary":
        return f"main server ({server})"
    if role == "standby":
        return f"backup server ({server})"
    return f"server {server}"


def health_status_text(snapshot: Optional[DifyServerHealth]) -> str:
    """Plain-language health status for heartbeat summaries."""
    if snapshot is None:
        return "not checked yet"
    if snapshot.online:
        return "online"
    threshold = HEALTH_FAILURE_THRESHOLD
    failures = snapshot.consecutive_failures
    if snapshot.considered_down:
        return f"offline ({failures} failed checks)"
    return f"unstable ({failures} of {threshold} failed checks)"


def probe_failure_reason(http_status: Optional[int], err: Optional[str]) -> str:
    """Short explanation of why a probe failed."""
    if http_status is not None:
        return f"HTTP {http_status}"
    if err == "timeout":
        return "request timed out"
    if err == "api_key_not_configured":
        return "API key is missing"
    if err == "base_url_not_configured":
        return "API URL is missing"
    if err:
        return err.replace("_", " ")
    return "probe failed"


def traffic_route_sentence(
    active_route: Optional[int],
    primary: int,
    standby: int,
    primary_health: Optional[DifyServerHealth],
    standby_health: Optional[DifyServerHealth],
) -> str:
    """Explain which server MindMate traffic is using."""
    if active_route == standby:
        return "MindMate uses backup server — failover active."
    if active_route == primary:
        primary_down = primary_health is not None and primary_health.considered_down
        standby_down = standby_health is not None and standby_health.considered_down
        if primary_down and standby_down:
            return "MindMate stays on main server (both servers unreachable)."
        if primary_health is not None and not primary_health.online and not primary_health.considered_down:
            return "MindMate still uses main server (failover not triggered yet)."
        return "MindMate uses main server."
    if active_route is None:
        return "MindMate routing is not configured."
    return f"MindMate uses server {active_route}."
