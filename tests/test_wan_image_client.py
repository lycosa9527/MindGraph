"""Unit tests for Wan 2.7 async image client helpers."""

from __future__ import annotations

from services.t2i.wan_image_client import (
    clamp_wan_n,
    extract_image_urls_from_task_output,
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
