"""Tests for MindMate export date-range overlap helpers."""

from __future__ import annotations

import main as _main_app

assert _main_app.app.title

from services.dify.export.time_range import activity_overlaps_range, conversation_overlaps_export_range


def test_conversation_overlap_matches_created_and_updated() -> None:
    """Dify rows use created/updated bounds for overlap."""
    assert conversation_overlaps_export_range(50, 550, 400, 600) is True
    assert conversation_overlaps_export_range(0, 450, 400, 600) is True
    assert conversation_overlaps_export_range(650, 700, 400, 600) is False


def test_open_ended_range() -> None:
    """Missing start or end is treated as unbounded on that side."""
    assert activity_overlaps_range(100, 200, 150, None) is True
    assert activity_overlaps_range(100, 200, 250, None) is False
    assert activity_overlaps_range(100, 200, None, 150) is True
    assert activity_overlaps_range(100, 200, None, 50) is False
