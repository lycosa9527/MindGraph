"""Chat-handoff pairing SSE doorbell helpers."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from services.knowledge.chat_handoff_sse import (
    format_handoff_sse,
    frame_from_handoff_payload,
    handoff_wake_channel,
    publish_handoff_status,
)


def test_handoff_status_frame_is_small() -> None:
    """Desktop EventSource only needs status + package ids."""
    frame = format_handoff_sse("done", 3, 9)
    assert frame.startswith("event: status\n")
    assert '"status":"done"' in frame
    assert '"package_id":3' in frame
    assert '"document_id":9' in frame


def test_handoff_payload_roundtrip() -> None:
    """Redis publish payload frames as a status event."""
    raw = json.dumps({"status": "received", "package_id": 4, "document_id": None})
    assert frame_from_handoff_payload(raw) == format_handoff_sse("received", 4, None)


@pytest.mark.asyncio
async def test_publish_handoff_status_uses_code_channel() -> None:
    """Status changes wake only the waiting pairing code."""
    redis = AsyncMock()
    with patch(
        "services.knowledge.chat_handoff_sse.get_async_redis",
        return_value=redis,
    ):
        await publish_handoff_status("123456", "indexing", 7, None)
    redis.publish.assert_awaited_once()
    channel, payload = redis.publish.await_args.args
    assert channel == handoff_wake_channel("123456")
    parsed = json.loads(payload)
    assert parsed["status"] == "indexing"
    assert parsed["package_id"] == 7
