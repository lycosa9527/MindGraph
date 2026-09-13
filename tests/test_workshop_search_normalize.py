"""ILIKE fallback must escape % and _ like the org roster search."""

from services.features.workshop_chat.message_search_normalize import ilike_pattern_from_text


def test_ilike_pattern_escapes_wildcards() -> None:
    """A literal percent must not become a match-all search."""
    pattern, lim = ilike_pattern_from_text("100%", 40)
    assert pattern == r"%100\%%"
    assert lim == 40
