"""Black, white, Siamese, raven, and schnauzer green-screen stills stay in the repo."""

from __future__ import annotations

from scripts.cat_emoji.paths import (
    BLACK_STILL_FRONT,
    BLACK_STILL_THREE_QUARTER,
    RAVEN_STILL_FRONT,
    SCHNAUZER_STILL_FRONT,
    SIAMESE_STILL_FRONT,
    SIAMESE_STILL_THREE_QUARTER,
    WHITE_STILL_FRONT,
    WHITE_STILL_THREE_QUARTER,
)


def test_all_cats_have_repo_greenscreen_stills() -> None:
    """Front and 3/4 cat stills, plus raven and schnauzer fronts, are committed source."""
    for still in (
        BLACK_STILL_FRONT,
        BLACK_STILL_THREE_QUARTER,
        WHITE_STILL_FRONT,
        WHITE_STILL_THREE_QUARTER,
        SIAMESE_STILL_FRONT,
        SIAMESE_STILL_THREE_QUARTER,
        RAVEN_STILL_FRONT,
        SCHNAUZER_STILL_FRONT,
    ):
        assert still.is_file(), still
        assert still.stat().st_size > 100_000
        assert "scripts/cat_emoji/stills/" in still.as_posix()
