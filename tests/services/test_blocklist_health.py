"""Blocklist version fields on the health probe."""

from __future__ import annotations

from services.infrastructure.monitoring.health_checks.blocklists import (
    blocklist_health_status,
    describe_blocklist_feed,
)


def test_describe_blocklist_feed_reports_dates():
    """Both dates come from the snapshot timestamp, not the COS upload clock."""
    status = {
        "local_meta": {
            "last_merge_unix": 1_700_000_000,
            "count": 12,
        },
        "cos_meta": {
            "uploaded_at": "2026-09-27T00:00:00+00:00",
            "count": 12,
            "last_merge_unix": 1_700_000_030,
        },
    }
    feed = describe_blocklist_feed(status, compare=True, enabled=True)
    assert feed["count"] == 12
    assert feed["version"] == "2023-11-14T22:13:20+00:00"
    assert feed["cos_version"] == "2023-11-14T22:13:50+00:00"
    assert feed["newest"] is True
    assert "sha256" not in feed


def test_describe_blocklist_feed_behind_when_local_date_is_older():
    """An older local date means this server does not have the newest database."""
    status = {
        "local_meta": {"last_merge_unix": 1_700_000_000, "count": 1},
        "cos_meta": {"last_merge_unix": 1_700_086_400, "count": 2},
    }
    feed = describe_blocklist_feed(status, compare=True, enabled=True)
    assert feed["newest"] is False


def test_blocklist_health_status_skips_when_unused():
    """Unused feeds do not affect the health summary."""
    empty = describe_blocklist_feed({}, compare=False, enabled=False)
    assert blocklist_health_status(empty, empty) == "skipped"


def test_blocklist_health_status_stays_healthy_when_one_feed_is_stale():
    """A stale database is visible on the feed and does not mark the server down."""
    current = describe_blocklist_feed(
        {
            "local_meta": {"last_merge_unix": 1_700_000_000},
            "cos_meta": {"last_merge_unix": 1_700_000_000},
        },
        compare=True,
        enabled=True,
    )
    stale = describe_blocklist_feed(
        {
            "local_meta": {"last_merge_unix": 1_700_000_000},
            "cos_meta": {"last_merge_unix": 1_700_086_400},
        },
        compare=True,
        enabled=True,
    )
    assert stale["newest"] is False
    assert blocklist_health_status(current, stale) == "healthy"
