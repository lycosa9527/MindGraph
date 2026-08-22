"""Allowlisted diagram source_channel values and exact list matching."""

import pytest

from services.diagram.source_channel import (
    filter_diagram_list_by_source_channel,
    list_items_missing_source_channel_field,
    parse_list_source_channel,
    resolve_diagram_source_channel,
)


def test_resolve_diagram_source_channel_defaults_and_allowlist() -> None:
    """Blank stores as mindgraph; unknown values are rejected."""
    assert resolve_diagram_source_channel(None) == "mindgraph"
    assert resolve_diagram_source_channel("  ") == "mindgraph"
    assert resolve_diagram_source_channel("voice_notes") == "voice_notes"
    with pytest.raises(ValueError):
        resolve_diagram_source_channel("kitty_voice")


def test_parse_list_source_channel_rejects_unknown() -> None:
    """List query only accepts the allowlist."""
    assert parse_list_source_channel(None) is None
    assert parse_list_source_channel("") is None
    assert parse_list_source_channel("voice_notes") == "voice_notes"
    with pytest.raises(ValueError):
        parse_list_source_channel("kitty_voice")


def test_filter_matches_stored_channel_only() -> None:
    """History identity is the column, not the title."""
    rows = [
        {"title": "voice recording_202608230012", "source_channel": None},
        {"title": "circle map", "source_channel": "mindgraph"},
        {"title": "Renamed", "source_channel": "voice_notes"},
    ]
    filtered = filter_diagram_list_by_source_channel(rows, "voice_notes")
    assert [row["title"] for row in filtered] == ["Renamed"]
    assert filter_diagram_list_by_source_channel(rows, None) == rows
    assert list_items_missing_source_channel_field([{"title": "x"}]) is True
    assert list_items_missing_source_channel_field([{"title": "x", "source_channel": None}]) is False
