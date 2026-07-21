"""Tests for unified module activity helper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.monitoring.module_activity import track_module_activity


@pytest.mark.asyncio
async def test_track_module_activity_logs_and_records(caplog: pytest.LogCaptureFixture) -> None:
    """Helper emits [UserActivity] INFO and calls Redis + usage schedule."""
    user = MagicMock()
    user.id = 42
    user.organization_id = 7
    user.phone = "13800000000"
    user.name = "Tester"

    tracker = MagicMock()
    tracker.record_activity = AsyncMock()

    with (
        patch(
            "services.monitoring.module_activity.get_activity_tracker",
            return_value=tracker,
        ),
        patch(
            "services.monitoring.module_activity.schedule_user_usage_activity",
        ) as schedule_usage,
        patch(
            "services.monitoring.module_activity.get_client_ip",
            return_value="1.2.3.4",
        ),
        patch(
            "services.monitoring.module_activity.client_source_from_request",
            return_value="web",
        ),
        caplog.at_level("INFO", logger="services.monitoring.module_activity"),
    ):
        await track_module_activity(
            user=user,
            module="canvas",
            redis_activity_type="diagram_generation",
            request=MagicMock(),
            details={"diagram_type": "mind_map"},
            detail="mind_map topic=photosynthesis",
            usage_source="mindgraph",
            usage_action="diagram_generate",
            title="Photosynthesis",
            prompt_preview="photosynthesis",
            diagram_type="mind_map",
        )

    assert tracker.record_activity.await_count == 1
    call_kwargs = tracker.record_activity.await_args.kwargs
    assert call_kwargs["user_id"] == 42
    assert call_kwargs["activity_type"] == "diagram_generation"
    assert call_kwargs["client_source"] == "web"
    schedule_usage.assert_called_once()
    usage_kwargs = schedule_usage.call_args.kwargs
    assert usage_kwargs["action"] == "diagram_generate"
    assert usage_kwargs["source"] == "mindgraph"
    assert any("[UserActivity]" in record.message for record in caplog.records)
    assert any("user=42" in record.message for record in caplog.records)
    assert any("module=canvas" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_track_module_activity_skips_invalid_user() -> None:
    """user_id <= 0 is a no-op."""
    with patch(
        "services.monitoring.module_activity.get_activity_tracker",
    ) as get_tracker:
        await track_module_activity(
            user_id=0,
            module="canvas",
            redis_activity_type="diagram_generation",
            persist_usage=False,
        )
    get_tracker.assert_not_called()


@pytest.mark.asyncio
async def test_track_module_activity_persist_usage_false() -> None:
    """Redis + log without scheduling usage timeline."""
    tracker = MagicMock()
    tracker.record_activity = AsyncMock()
    with (
        patch(
            "services.monitoring.module_activity.get_activity_tracker",
            return_value=tracker,
        ),
        patch(
            "services.monitoring.module_activity.schedule_user_usage_activity",
        ) as schedule_usage,
    ):
        await track_module_activity(
            user_id=9,
            organization_id=1,
            module="mindmate",
            redis_activity_type="ai_assistant",
            persist_usage=False,
        )
    tracker.record_activity.assert_awaited_once()
    schedule_usage.assert_not_called()
