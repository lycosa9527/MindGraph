"""Tests for admin-readable Dify failover log helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from models.domain.auth import Organization
from services.dify.dify_health_logging import (
    health_status_text,
    org_label,
    probe_failure_reason,
    server_label,
    traffic_route_sentence,
)
from services.redis.cache.redis_dify_server_health_cache import (
    HEALTH_FAILURE_THRESHOLD,
    DifyServerHealth,
)


def _org(**kwargs: object) -> Organization:
    defaults = {"id": 7, "name": "Example School", "display_name": None}
    defaults.update(kwargs)
    return cast(Organization, SimpleNamespace(**defaults))


def test_org_label_prefers_display_name() -> None:
    """School label uses display name when set."""
    org = _org(display_name="Springfield High")
    assert org_label(org) == '"Springfield High" (org 7)'


def test_server_label_uses_admin_terms() -> None:
    """Server labels use main/backup wording for admins."""
    assert server_label(1, "primary") == "main server (1)"
    assert server_label(2, "standby") == "backup server (2)"


def test_health_status_text_describes_failures() -> None:
    """Status text explains online, unstable, and offline states."""
    assert health_status_text(None) == "not checked yet"
    assert health_status_text(DifyServerHealth(True, 0, 1.0, 1.0)) == "online"
    unstable = DifyServerHealth(False, 1, None, 1.0)
    assert health_status_text(unstable) == f"unstable (1 of {HEALTH_FAILURE_THRESHOLD} failed checks)"
    offline = DifyServerHealth(False, HEALTH_FAILURE_THRESHOLD, None, 1.0)
    assert health_status_text(offline) == f"offline ({HEALTH_FAILURE_THRESHOLD} failed checks)"


def test_probe_failure_reason_is_plain_language() -> None:
    """Probe errors are readable without internal tokens."""
    assert probe_failure_reason(503, "http_503") == "HTTP 503"
    assert probe_failure_reason(None, "timeout") == "request timed out"


def test_traffic_route_sentence_describes_failover() -> None:
    """Routing sentence explains which server MindMate uses."""
    primary_health = DifyServerHealth(False, HEALTH_FAILURE_THRESHOLD, None, 1.0)
    standby_health = DifyServerHealth(True, 0, 1.0, 1.0)
    text = traffic_route_sentence(2, 1, 2, primary_health, standby_health)
    assert text == "MindMate uses backup server — failover active."
