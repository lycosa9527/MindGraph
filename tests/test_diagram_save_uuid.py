"""Regression: new diagrams must always receive a UUID (including unlimited tier)."""

from __future__ import annotations

from services.redis.cache.diagram_new_id import assign_id_for_new_diagram
from utils.auth.school_tier_defs import SCHOOL_TIER_DIAGRAM_LIMIT_UNLIMITED


def test_assign_id_for_unlimited_tier_user() -> None:
    """Production bug: unlimited users skipped UUID and hit id=None NotNullViolation."""
    diagram_id, error = assign_id_for_new_diagram(SCHOOL_TIER_DIAGRAM_LIMIT_UNLIMITED, 0)

    assert error is None
    assert diagram_id is not None
    assert len(diagram_id) == 36


def test_assign_id_blocked_when_trial_quota_full() -> None:
    diagram_id, error = assign_id_for_new_diagram(20, 20)

    assert diagram_id is None
    assert error is not None
    assert error.startswith("diagram_limit_reached:")


def test_assign_id_when_trial_quota_available() -> None:
    diagram_id, error = assign_id_for_new_diagram(20, 19)

    assert error is None
    assert diagram_id is not None
