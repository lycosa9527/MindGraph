"""Maite module activity must not coerce to canvas."""

from __future__ import annotations

from services.monitoring.module_activity import VALID_MODULES


def test_maite_is_valid_module_activity_key() -> None:
    """Maite must be a first-class module activity key."""
    assert "maite" in VALID_MODULES
