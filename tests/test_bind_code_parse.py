"""Tests for bind code parsing and display formatting."""

from services.mindbot.bind.code_parse import extract_bind_code_from_text, format_bind_code_display


def test_format_bind_code_display() -> None:
    """Six digits render as 000-000."""
    assert format_bind_code_display("123456") == "123-456"


def test_extract_bind_code_plain_digits() -> None:
    """Plain six-digit body is accepted."""
    assert extract_bind_code_from_text("123456") == "123456"


def test_extract_bind_code_hyphenated() -> None:
    """Hyphenated 000-000 body is accepted."""
    assert extract_bind_code_from_text("123-456") == "123456"


def test_extract_bind_code_ignores_chat() -> None:
    """Mixed chat text is not treated as a bind code."""
    assert extract_bind_code_from_text("my code is 123456") is None
