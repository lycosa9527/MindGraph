"""Tests for markdown table helpers used by document extraction."""

from __future__ import annotations

from services.knowledge.markdown_tables import rows_to_markdown_table, sheet_to_markdown


def test_rows_to_markdown_table_basic() -> None:
    """Header + body rows render as a GFM table."""
    md = rows_to_markdown_table([["Name", "Score"], ["Ada", 10], ["Bob", 8]])
    assert md.startswith("| Name | Score |")
    assert "| --- | --- |" in md
    assert "| Ada | 10 |" in md


def test_rows_to_markdown_table_single_row_synthesizes_header() -> None:
    """A single data row still produces a valid table with synthetic headers."""
    md = rows_to_markdown_table([["only", "row"]])
    assert "Col 1" in md
    assert "| only | row |" in md


def test_sheet_to_markdown_wraps_heading() -> None:
    """Sheet helper prefixes a markdown heading."""
    section = sheet_to_markdown("Grades", [["A", "B"], [1, 2]])
    assert section is not None
    assert section.startswith("## Grades\n\n")
