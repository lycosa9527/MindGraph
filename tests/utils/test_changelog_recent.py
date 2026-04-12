"""Tests for changelog_recent parser."""

from services.utils.changelog_recent import extract_recent_changelog_entries

_SAMPLE = """# Changelog

## [2.0.0] - 2026-01-02

### Added
- Second

## [1.0.0] - 2026-01-01

### Added
- First
"""


def test_extract_respects_limit_order_and_body():
    first = extract_recent_changelog_entries(_SAMPLE, 1)
    assert len(first) == 1
    assert first[0]["title"] == "[2.0.0] - 2026-01-02"
    assert "Second" in first[0]["body"]
    assert "First" not in first[0]["body"]

    two = extract_recent_changelog_entries(_SAMPLE, 2)
    assert len(two) == 2
    assert two[1]["title"] == "[1.0.0] - 2026-01-01"
    assert "First" in two[1]["body"]


def test_extract_zero_limit_returns_empty():
    assert not extract_recent_changelog_entries(_SAMPLE, 0)


def test_skips_preamble_before_first_version():
    text = """# Title

Intro line.

## [0.1.0] - 2025-12-01

### Fixed
- X
"""
    out = extract_recent_changelog_entries(text, 5)
    assert len(out) == 1
    assert out[0]["title"] == "[0.1.0] - 2025-12-01"
