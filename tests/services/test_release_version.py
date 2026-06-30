"""Tests for release version comparison."""

from __future__ import annotations

from services.infrastructure.sync.release_version import compare_release_versions


def test_compare_release_versions_equal():
    """Equal semver strings compare as zero."""
    assert compare_release_versions("5.6.3", "5.6.3") == 0
    assert compare_release_versions("v1.18.1", "1.18.1") == 0
