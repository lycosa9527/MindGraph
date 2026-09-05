"""Packed stills and Wan catalog stay aligned with shipped role ids."""

from __future__ import annotations

from unittest.mock import patch

from scripts.training_roles.catalog import (
    ROLE_ACTIONS,
    assert_catalog_aligned,
    catalog_ids,
    role_clip_id,
)
from scripts.training_roles.paths import STILL_FRONT, STILL_THREE_QUARTER, STILLS_DIR
from scripts.training_roles.publish_packed import publish_prefix
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


def test_publish_prefix_skips_matching_objects() -> None:
    """Already-uploaded packed roles are not written again."""
    with (
        patch("scripts.training_roles.publish_packed._object_matches", return_value=True),
        patch("scripts.training_roles.publish_packed.upload_bytes") as upload,
    ):
        uploaded, skipped, failed = publish_prefix("training/mindgraph-Test")
    assert (uploaded, skipped, failed) == (0, 40, 0)
    upload.assert_not_called()
