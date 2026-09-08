"""Black and white green-screen stills stay in the repo."""

from __future__ import annotations

from scripts.cat_emoji.paths import (
    BLACK_STILL_FRONT,
    BLACK_STILL_THREE_QUARTER,
    WHITE_STILL_FRONT,
    WHITE_STILL_THREE_QUARTER,
)


def test_both_cats_have_repo_greenscreen_stills() -> None:
    """Front and 3/4 stills are committed source, not desktop-only."""
    for still in (
        BLACK_STILL_FRONT,
        BLACK_STILL_THREE_QUARTER,
        WHITE_STILL_FRONT,
        WHITE_STILL_THREE_QUARTER,
    ):
        assert still.is_file(), still
        assert still.stat().st_size > 100_000
        assert "scripts/cat_emoji/stills/" in still.as_posix()
