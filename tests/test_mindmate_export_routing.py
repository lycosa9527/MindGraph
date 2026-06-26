"""Tests for MindMate export sync vs background routing."""

from __future__ import annotations

from services.dify.export.export_routing import should_use_background_job


def test_scope_all_always_background() -> None:
    """Export scope all always uses a background job."""
    assert should_use_background_job("all", 1) is True
    assert should_use_background_job("all", 0) is True


def test_user_count_threshold() -> None:
    """User count above the sync threshold triggers a background job."""
    assert should_use_background_job("whole", 50) is False
    assert should_use_background_job("whole", 51) is True


def test_conversation_count_threshold() -> None:
    """Conversation count above the sync threshold triggers a background job."""
    assert should_use_background_job("users", 1, conversation_count=500) is False
    assert should_use_background_job("users", 1, conversation_count=501) is True
