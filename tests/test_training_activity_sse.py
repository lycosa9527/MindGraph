"""Activity roster and SSE doorbell helpers."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from services.features.training.activity_store import activity_summary, list_activity, touch_activity
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


def test_format_sse_ended_event() -> None:
    """Ended frames stay small."""
    frame = format_sse("ended", {"seq": 12})
    assert frame.startswith("event: ended\n")
    assert '"seq":12' in frame
