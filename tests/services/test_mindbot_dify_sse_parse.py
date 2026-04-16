"""Tests for core/dify_sse_parse.py (message_file, TTS, workflow, blocking file parsing)."""

from __future__ import annotations

import base64

import pytest

from services.mindbot.core.dify_sse_parse import (
    is_image_file_type,
    parse_blocking_message_files,
    parse_message_file_event,
    parse_tts_audio_base64_chunk,
    workflow_outputs_file_hints,
)


# ---------------------------------------------------------------------------
# parse_message_file_event
# ---------------------------------------------------------------------------


def test_parse_message_file_event_nested_data_url() -> None:
    ev = {"data": {"url": "https://example.com/img.png", "type": "image/png"}}
    result = parse_message_file_event(ev)
    assert result is not None
    assert result["url"] == "https://example.com/img.png"
    assert result["type"] == "image"


def test_parse_message_file_event_top_level_url() -> None:
    ev = {"url": "https://example.com/doc.pdf", "type": "document"}
    result = parse_message_file_event(ev)
    assert result is not None
    assert result["url"] == "https://example.com/doc.pdf"
    assert result["type"] == "document"


def test_parse_message_file_event_infers_image_from_jpg_extension() -> None:
    ev = {"url": "https://cdn.example.com/photo.jpg"}
    result = parse_message_file_event(ev)
    assert result is not None
    assert result["type"] == "image"


def test_parse_message_file_event_infers_document_for_other_extension() -> None:
    ev = {"url": "https://cdn.example.com/report.docx"}
    result = parse_message_file_event(ev)
    assert result is not None
    assert result["type"] == "document"


def test_parse_message_file_event_missing_url_returns_none() -> None:
    assert parse_message_file_event({}) is None
    assert parse_message_file_event({"data": {}}) is None


def test_parse_message_file_event_whitespace_url_returns_none() -> None:
    assert parse_message_file_event({"url": "   "}) is None


def test_parse_message_file_event_extracts_file_id() -> None:
    ev = {"url": "https://cdn/f.png", "id": "file-42", "type": "image"}
    result = parse_message_file_event(ev)
    assert result is not None
    assert result["file_id"] == "file-42"


def test_parse_message_file_event_remote_url_fallback() -> None:
    ev = {"data": {"remote_url": "https://remote.example.com/img.png"}}
    result = parse_message_file_event(ev)
    assert result is not None
    assert result["url"] == "https://remote.example.com/img.png"


# ---------------------------------------------------------------------------
# parse_tts_audio_base64_chunk
# ---------------------------------------------------------------------------


def test_parse_tts_audio_base64_valid() -> None:
    payload = b"hello audio"
    encoded = base64.b64encode(payload).decode()
    ev = {"audio": encoded}
    result = parse_tts_audio_base64_chunk(ev)
    assert result == payload


def test_parse_tts_audio_base64_from_nested_data() -> None:
    payload = b"audio-data"
    encoded = base64.b64encode(payload).decode()
    ev = {"data": {"audio": encoded}}
    result = parse_tts_audio_base64_chunk(ev)
    assert result == payload


def test_parse_tts_audio_raw_bytes_returned_directly() -> None:
    raw = b"raw-bytes"
    ev = {"audio": raw}
    result = parse_tts_audio_base64_chunk(ev)
    assert result == raw


def test_parse_tts_audio_missing_returns_none() -> None:
    assert parse_tts_audio_base64_chunk({}) is None


def test_parse_tts_audio_empty_string_returns_none() -> None:
    assert parse_tts_audio_base64_chunk({"audio": ""}) is None


def test_parse_tts_audio_whitespace_returns_none() -> None:
    assert parse_tts_audio_base64_chunk({"audio": "   "}) is None


# ---------------------------------------------------------------------------
# is_image_file_type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "type_s",
    ["image", "image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp", "IMAGE/PNG"],
)
def test_is_image_file_type_truthy(type_s: str) -> None:
    assert is_image_file_type(type_s)


@pytest.mark.parametrize("type_s", ["document", "audio", "video", "", "pdf", "text/plain"])
def test_is_image_file_type_falsy(type_s: str) -> None:
    assert not is_image_file_type(type_s)


# ---------------------------------------------------------------------------
# workflow_outputs_file_hints
# ---------------------------------------------------------------------------


def test_workflow_outputs_file_hints_list_value() -> None:
    outputs = {
        "files": [
            {"url": "https://cdn/a.png", "type": "image"},
            {"url": "https://cdn/b.pdf", "type": "document"},
        ]
    }
    hints = workflow_outputs_file_hints(outputs)
    urls = [h["url"] for h in hints]
    assert "https://cdn/a.png" in urls
    assert "https://cdn/b.pdf" in urls


def test_workflow_outputs_file_hints_dict_value() -> None:
    outputs = {"output_file": {"url": "https://cdn/result.png", "type": "image"}}
    hints = workflow_outputs_file_hints(outputs)
    assert any(h["url"] == "https://cdn/result.png" for h in hints)


def test_workflow_outputs_file_hints_deduplicates_urls() -> None:
    outputs = {
        "f1": {"url": "https://cdn/x.png"},
        "f2": [{"url": "https://cdn/x.png"}],
    }
    hints = workflow_outputs_file_hints(outputs)
    urls = [h["url"] for h in hints]
    assert urls.count("https://cdn/x.png") == 1


def test_workflow_outputs_file_hints_empty_outputs() -> None:
    assert workflow_outputs_file_hints({}) == []


def test_workflow_outputs_file_hints_no_url_field_ignored() -> None:
    outputs = {"f1": {"name": "doc.pdf"}}
    assert workflow_outputs_file_hints(outputs) == []


def test_workflow_outputs_file_hints_non_dict_list_items_skipped() -> None:
    outputs = {"files": ["not-a-dict", 42, None]}
    assert workflow_outputs_file_hints(outputs) == []


# ---------------------------------------------------------------------------
# parse_blocking_message_files
# ---------------------------------------------------------------------------


def test_parse_blocking_message_files_from_metadata() -> None:
    resp = {
        "metadata": {
            "message_files": [
                {"url": "https://cdn/img.png", "type": "image/png"},
            ]
        }
    }
    files = parse_blocking_message_files(resp)
    assert len(files) >= 1
    assert files[0]["url"] == "https://cdn/img.png"


def test_parse_blocking_message_files_top_level_key() -> None:
    resp = {
        "message_files": [
            {"url": "https://cdn/doc.pdf", "type": "document"},
        ]
    }
    files = parse_blocking_message_files(resp)
    assert any(f["url"] == "https://cdn/doc.pdf" for f in files)


def test_parse_blocking_message_files_no_url_skipped() -> None:
    resp = {"message_files": [{"type": "image", "filename": "test.png"}]}
    assert parse_blocking_message_files(resp) == []


def test_parse_blocking_message_files_empty_response() -> None:
    assert parse_blocking_message_files({}) == []


def test_parse_blocking_message_files_preview_url_fallback() -> None:
    resp = {
        "message_files": [{"preview_url": "https://cdn/preview.jpg", "type": "image"}]
    }
    files = parse_blocking_message_files(resp)
    assert any(f["url"] == "https://cdn/preview.jpg" for f in files)
