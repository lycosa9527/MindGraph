"""Smoke tests for diagram spine channel adapter registration."""

from services.agent_hub.diagram_spine.origins import (
    list_registered_channel_adapters,
    register_channel_adapter,
    reset_channel_adapters_for_tests,
)


def test_mindmate_adapter_can_register() -> None:
    """MindMate stub adapter registers through register_channel_adapter."""
    reset_channel_adapters_for_tests()
    register_channel_adapter("mindmate")
    assert "mindmate" in list_registered_channel_adapters()
    reset_channel_adapters_for_tests()


def test_register_channel_adapter_idempotent() -> None:
    """Duplicate adapter registration is ignored."""
    reset_channel_adapters_for_tests()
    register_channel_adapter("mindmate")
    register_channel_adapter("mindmate")
    assert list_registered_channel_adapters().count("mindmate") == 1
    reset_channel_adapters_for_tests()
