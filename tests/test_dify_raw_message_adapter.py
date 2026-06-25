"""Tests for raw Dify message row adapter."""

from __future__ import annotations

import main as _main_app

assert _main_app.app.title

from services.dify.export.raw_message_adapter import row_to_api_message


def test_row_to_api_message_maps_fields() -> None:
    row = {
        "id": "m1",
        "conversation_id": "c1",
        "query": "question",
        "answer": "answer",
        "created_at": "2024-06-01 12:00:00",
        "status": "normal",
    }
    message = row_to_api_message(
        row,
        files=[{"id": "f1", "url": "https://x"}],
        feedback_rating="dislike",
    )
    assert message["id"] == "m1"
    assert message["created_at"] > 0
    assert message["feedback"]["rating"] == "dislike"
    assert message["message_files"][0]["url"] == "https://x"
