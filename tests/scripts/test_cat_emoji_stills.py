"""Black, white, Siamese, raven, and schnauzer green-screen stills stay in the repo."""

from __future__ import annotations

from PIL import Image

from scripts.cat_emoji.paths import (
    BLACK_STILL_FRONT,
    BLACK_STILL_THREE_QUARTER,
    RAVEN_STILL_FRONT,
    RAVEN_STILL_THREE_QUARTER,
    SCHNAUZER_STILL_FRONT,
    SCHNAUZER_STILL_THREE_QUARTER,
    SIAMESE_STILL_FRONT,
    SIAMESE_STILL_THREE_QUARTER,
    WHITE_STILL_FRONT,
    WHITE_STILL_THREE_QUARTER,
)

REFERENCE_SIZE = (1280, 1920)


def test_all_roles_have_repo_greenscreen_stills() -> None:
    """Each of the five roles keeps both green-screen reference stills in git."""
    for still in (
        BLACK_STILL_FRONT,
        BLACK_STILL_THREE_QUARTER,
        WHITE_STILL_FRONT,
        WHITE_STILL_THREE_QUARTER,
        SIAMESE_STILL_FRONT,
        SIAMESE_STILL_THREE_QUARTER,
        RAVEN_STILL_FRONT,
        RAVEN_STILL_THREE_QUARTER,
        SCHNAUZER_STILL_FRONT,
        SCHNAUZER_STILL_THREE_QUARTER,
    ):
        assert still.is_file(), still
        assert still.stat().st_size > 100_000
        assert "scripts/cat_emoji/stills/" in still.as_posix()
        with Image.open(still) as image:
            assert image.size == REFERENCE_SIZE, still
