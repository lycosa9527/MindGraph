"""Activity roster and SSE doorbell helpers."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from services.features.training.activity_store import (
    activity_summary,
    list_activity,
    should_publish_activity,
    touch_activity,
)
from services.features.training.payloads import sanitize_activity_page_key
from services.features.training.constants import EVENTS_CHANNEL
from services.features.training.sse import format_sse, frame_from_payload, publish_event
from tests.test_training_session_store import FakeRedis


def _patch_activity_redis(redis: FakeRedis):
    return patch(
        "services.features.training.activity_store.get_async_redis",
        return_value=redis,
    )


def _patch_sse_redis(redis: FakeRedis):
    return patch(
        "services.features.training.sse.get_async_redis",
        return_value=redis,
    )


@pytest.mark.asyncio
async def test_roster_summary_over_200_activity_keys() -> None:
    """Paged roster join stays correct above 200 heartbeats."""
    redis = FakeRedis()
    now = time.time()
    with _patch_activity_redis(redis):
        for index in range(210):
            state = "generating" if index < 15 else "done" if index < 40 else "idle"
            await touch_activity(
                8,
                index + 1,
                {
                    "name": f"T{index}",
                    "generate_state": state,
                    "diagram_type": "double_bubble_map",
                    "updated_at": now,
                },
            )
        rows = await list_activity(8)
        summary = await activity_summary(8)
    assert len(rows) == 210
    assert summary["online"] == 210
    assert summary["generating"] == 15
    assert summary["done"] == 25
    page = rows[0:50]
    assert len(page) == 50


@pytest.mark.asyncio
async def test_sse_body_is_seq_only_and_reaches_other_worker() -> None:
    """Publish is a tiny seq envelope another worker can frame."""
    redis = FakeRedis()
    with _patch_sse_redis(redis):
        await publish_event(3, "seq", {"seq": 8})
    assert redis.published
    channel, payload = redis.published[0]
    assert channel == EVENTS_CHANNEL.format(org_id=3)
    frame = frame_from_payload(payload)
    assert frame is not None
    assert frame == format_sse("seq", {"seq": 8})
    assert "diagram_type" not in frame
    assert "topic_options" not in frame
    assert '"seq":8' in frame


@pytest.mark.asyncio
async def test_activity_merge_keeps_topic_across_idle_heartbeat() -> None:
    """Idle page heartbeats must not wipe the last topic chip."""
    redis = FakeRedis()
    with _patch_activity_redis(redis):
        await touch_activity(
            8,
            3,
            {
                "name": "Ada",
                "generate_state": "done",
                "diagram_type": "double_bubble_map",
                "option_label": "ice vs water",
                "page_key": "canvas",
            },
        )
        await touch_activity(
            8,
            3,
            {
                "name": "Ada",
                "generate_state": "idle",
                "diagram_type": "double_bubble_map",
                "page_key": "mindmate",
            },
        )
        rows = await list_activity(8)
    assert rows[0]["option_label"] == "ice vs water"
    assert rows[0]["page_key"] == "mindmate"
    assert rows[0]["generate_state"] == "idle"


@pytest.mark.asyncio
async def test_activity_sse_gate_is_once_per_second() -> None:
    """Teacher heartbeats do not doorbell the whole org every 10s."""
    redis = FakeRedis()
    with _patch_activity_redis(redis):
        first = await should_publish_activity(4)
        second = await should_publish_activity(4)
    assert first is True
    assert second is False


def test_sanitize_activity_page_key_allows_known_pages() -> None:
    """Activity page keys stay on the course catalog plus slide/video."""
    assert sanitize_activity_page_key("mindmate") == "mindmate"
    assert sanitize_activity_page_key("slide") == "slide"
    assert sanitize_activity_page_key("/evil") is None


def test_format_sse_ended_event() -> None:
    """Ended frames stay small."""
    frame = format_sse("ended", {"seq": 12})
    assert frame.startswith("event: ended\n")
    assert '"seq":12' in frame
