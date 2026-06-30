"""Tests for Qdrant COS sync."""

from __future__ import annotations

from services.infrastructure.sync import qdrant_cos_sync
from services.infrastructure.sync.release_version import compare_release_versions


def test_qdrant_update_status_not_on_cos():
    """Missing COS meta yields not_on_cos."""
    assert qdrant_cos_sync.qdrant_update_status("1.18.1", "1.18.0", None) == "not_on_cos"


def test_qdrant_update_status_up_to_date():
    """Installed version matching COS meta is up_to_date."""
    meta = {"version": "1.18.1"}
    assert qdrant_cos_sync.qdrant_update_status("1.18.1", "1.18.1", meta) == "up_to_date"


def test_compare_release_versions():
    """Semver ordering ignores leading v and compares numeric parts."""
    assert compare_release_versions("1.18.0", "1.18.1") == -1
    assert compare_release_versions("1.19.0", "1.18.1") == 1


def test_qdrant_cos_update_needed_cos_newer(monkeypatch):
    """COS newer than installed triggers cos_newer."""
    monkeypatch.setattr(
        qdrant_cos_sync,
        "read_qdrant_cos_meta",
        lambda: {"version": "1.18.2"},
    )
    monkeypatch.setattr(
        qdrant_cos_sync,
        "detect_installed_qdrant_version",
        lambda: "1.18.1",
    )
    plan = qdrant_cos_sync.qdrant_cos_update_needed()
    assert plan["update_needed"] is True
    assert plan["reason"] == "cos_newer"
    assert plan["cos_version"] == "1.18.2"


def test_qdrant_cos_update_needed_up_to_date(monkeypatch):
    """Matching installed and COS versions are up_to_date."""
    monkeypatch.setattr(
        qdrant_cos_sync,
        "read_qdrant_cos_meta",
        lambda: {"version": "1.18.2"},
    )
    monkeypatch.setattr(
        qdrant_cos_sync,
        "detect_installed_qdrant_version",
        lambda: "1.18.2",
    )
    plan = qdrant_cos_sync.qdrant_cos_update_needed()
    assert plan["update_needed"] is False
    assert plan["reason"] == "up_to_date"
