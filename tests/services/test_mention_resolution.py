"""Tests for workshop chat @**Name** parsing."""

from services.features.workshop_chat.mention_resolution import (
    parse_mention_display_names,
)


def test_parse_mention_display_names_empty():
    assert parse_mention_display_names("") == []
    assert parse_mention_display_names("no mentions here") == []


def test_parse_mention_display_names_single():
    assert parse_mention_display_names("hi @**Ada Lovelace**") == ["Ada Lovelace"]


def test_parse_mention_display_names_unique_order():
    text = "@**Bob** and @**Ann** and again @**Bob**"
    assert parse_mention_display_names(text) == ["Bob", "Ann"]


def test_parse_mention_display_names_strips_inner_spaces():
    assert parse_mention_display_names("@**  trim  **") == ["trim"]
