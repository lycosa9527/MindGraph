"""Unit tests for Wan 2.7 async image client helpers."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from services.infrastructure.http.error_handler import LLMProviderError
from services.t2i import wan_image_client
from services.t2i.wan_image_client import (
    clamp_wan_n,
    extract_image_urls_from_task_output,
    poll_wan_image_task,
)


def test_clamp_wan_n() -> None:
    """Clamp Wan n to DashScope allowed range."""
    assert clamp_wan_n(0) == 1
    assert clamp_wan_n(4) == 4
    assert clamp_wan_n(99) == 12


def test_extract_image_urls_ordered() -> None:
    """Preserve choice content order when collecting image URLs."""
    output = {
        "task_status": "SUCCEEDED",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "image", "image": "https://example.com/a.png"},
                        {"type": "image", "image": "https://example.com/b.png"},
                    ],
                },
            }
        ],
    }
    assert extract_image_urls_from_task_output(output) == [
        "https://example.com/a.png",
        "https://example.com/b.png",
    ]


def test_extract_image_urls_empty() -> None:
    """Missing or empty task output yields no URLs."""
    assert not extract_image_urls_from_task_output({})
    assert not extract_image_urls_from_task_output(None)


@pytest.mark.asyncio
async def test_poll_wan_image_task_logs_waiting_heartbeat(caplog: pytest.LogCaptureFixture) -> None:
    """Emit Waiting heartbeats while Wan reports PENDING/RUNNING."""
    responses: list[dict[str, Any]] = [
        {"output": {"task_status": "PENDING"}},
        {"output": {"task_status": "RUNNING"}},
        {
            "output": {
                "task_status": "SUCCEEDED",
                "choices": [
                    {
                        "message": {
                            "content": [{"type": "image", "image": "https://example.com/x.png"}],
                        }
                    }
                ],
            },
            "usage": {"size": "1920*1080", "image_count": 1},
        },
    ]

    with (
        patch.object(wan_image_client, "_dashscope_api_key", return_value="test-key"),
        patch.object(wan_image_client, "_api_v1_base", return_value="https://example.test/api/v1"),
        patch.object(wan_image_client, "_request_json", side_effect=responses),
        patch.object(wan_image_client.asyncio, "sleep", return_value=None),
        caplog.at_level("INFO", logger="services.t2i.wan_image_client"),
    ):
        result = await poll_wan_image_task(
            "task-abc",
            poll_interval=0.01,
            timeout_seconds=420.0,
            log_context="conversation=conv-1 batch=1/2",
        )

    assert result.task_id == "task-abc"
    assert result.image_urls == ("https://example.com/x.png",)
    waiting = [record.message for record in caplog.records if "Waiting" in record.message]
    assert waiting
    assert "task_id=task-abc" in waiting[0]
    assert "conversation=conv-1 batch=1/2" in waiting[0]
    succeeded = [record.message for record in caplog.records if "Succeeded" in record.message]
    assert succeeded
    assert "conversation=conv-1 batch=1/2" in succeeded[0]


@pytest.mark.asyncio
async def test_poll_wan_image_task_logs_timeout(caplog: pytest.LogCaptureFixture) -> None:
    """Log Timed out when the poll deadline elapses."""
    real_loop = asyncio.get_running_loop()
    times = [10.0, 50.0]

    def fake_time() -> float:
        if times:
            return times.pop(0)
        return 50.0

    with (
        patch.object(wan_image_client, "_dashscope_api_key", return_value="test-key"),
        patch.object(wan_image_client, "_api_v1_base", return_value="https://example.test/api/v1"),
        patch.object(real_loop, "time", side_effect=fake_time),
        caplog.at_level("ERROR", logger="services.t2i.wan_image_client"),
    ):
        with pytest.raises(LLMProviderError, match="timed out"):
            await poll_wan_image_task(
                "task-timeout",
                poll_interval=0.01,
                timeout_seconds=30.0,
                log_context="conversation=conv-x",
            )

    timed_out = [record.message for record in caplog.records if "Timed out" in record.message]
    assert timed_out
    assert "task_id=task-timeout" in timed_out[0]
    assert "conversation=conv-x" in timed_out[0]
