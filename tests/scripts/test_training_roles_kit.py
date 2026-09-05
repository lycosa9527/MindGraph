"""Packed stills and Wan catalog stay aligned with shipped role ids."""

from __future__ import annotations

from scripts.training_roles.catalog import (
    ROLE_ACTIONS,
    assert_catalog_aligned,
    catalog_ids,
    role_clip_id,
)
from scripts.training_roles.paths import STILL_FRONT, STILL_THREE_QUARTER, STILLS_DIR
from services.features.training.roles.catalog import TRAINING_ROLE_IDS


def test_original_stills_are_in_the_repo() -> None:
    """Both green-screen stills are committed source, not desktop-only."""
    assert STILLS_DIR.is_dir()
    assert STILL_FRONT.is_file()
    assert STILL_THREE_QUARTER.is_file()
    assert STILL_FRONT.stat().st_size > 100_000
    assert STILL_THREE_QUARTER.stat().st_size > 100_000


def test_wan_catalog_matches_shipped_role_ids() -> None:
    """Prompt ids match frontend/COS packed ids."""
    assert_catalog_aligned()
    assert catalog_ids() == TRAINING_ROLE_IDS
    assert role_clip_id(ROLE_ACTIONS[10]) == "11-clap"
