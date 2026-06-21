"""Tests for learning sheet result detection."""

from __future__ import annotations

from services.auth.thinking_coin.usage_wire import result_is_learning_sheet


def test_result_is_learning_sheet_top_level() -> None:
    """Detect flag on workflow result root."""
    assert result_is_learning_sheet({"is_learning_sheet": True}) is True


def test_result_is_learning_sheet_in_spec() -> None:
    """Detect flag nested in spec payload."""
    assert result_is_learning_sheet({"spec": {"is_learning_sheet": True}}) is True


def test_result_is_learning_sheet_false_when_missing() -> None:
    """Regular diagrams are not learning sheets."""
    assert result_is_learning_sheet({"spec": {"nodes": []}}) is False
