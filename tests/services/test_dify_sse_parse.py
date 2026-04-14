"""Unit tests for Dify SSE / blocking payload parsing (no HTTP)."""

from __future__ import annotations

import pytest

from services.mindbot.core.dify_sse_parse import (
    parse_blocking_message_files,
    parse_message_file_event,
    workflow_outputs_file_hints,
)


def test_parse_message_file_nested_data() -> None:
    ev = {
        "event": "message_file",
        "data": {
            "type": "image",
            "url": "https://cdn.example.com/f.png",
            "id": "file-1",
            "filename": "f.png",
        },
    }
    out = parse_message_file_event(ev)
    assert out is not None
    assert out["url"].startswith("https://")
    assert out["type"] == "image"


def test_workflow_outputs_file_hints_explicit_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINDBOT_DIFY_WORKFLOW_FILE_KEYS", "files_out")
    outputs = {
        "files_out": [
            {"url": "https://x.com/a.pdf", "type": "document", "filename": "a.pdf"},
        ],
    }
    hints = workflow_outputs_file_hints(outputs)
    assert len(hints) == 1
    assert hints[0]["url"].startswith("https://")


def test_parse_blocking_message_files_metadata() -> None:
    resp = {
        "answer": "ok",
        "metadata": {
            "message_files": [
                {"url": "https://z.com/i.jpg", "type": "image/jpeg", "filename": "i.jpg"},
            ],
        },
    }
    files = parse_blocking_message_files(resp)
    assert len(files) == 1
    assert "jpg" in files[0]["url"]
