"""Tests for File Center audio (ASR), vision OCR parsing, and audio hosting.

Covers the document-ingestion additions: audio MIME canonicalization/support,
DashScope vision-OCR response parsing, the async ASR result-URL collection and
transcript download, and the token-gated audio hosting helpers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from types import SimpleNamespace
from typing import Any, cast

import pytest

from services.knowledge import audio_hosting
from services.knowledge.audio_transcription import (
    AUDIO_EXTENSIONS,
    _collect_transcription_urls,
    _download_transcript_text,
    is_audio_mime,
)
from services.knowledge.document_ocr import _parse_vision_ocr_text
from services.knowledge.document_processor import get_document_processor


def test_is_audio_mime() -> None:
    """Audio MIME types are recognized; non-audio and None are rejected."""
    assert is_audio_mime("audio/mpeg") is True
    assert is_audio_mime("audio/wav") is True
    assert is_audio_mime("application/pdf") is False
    assert is_audio_mime(None) is False


def test_processor_supports_and_canonicalizes_audio() -> None:
    """All audio MIME types are supported and extensions canonicalize correctly."""
    processor = get_document_processor()
    for mime in set(AUDIO_EXTENSIONS.values()):
        assert processor.is_supported(mime), mime
    # mimetypes is inconsistent for .wav/.m4a/.opus; canonicalization must win.
    assert processor.get_file_type("lecture.wav") == "audio/wav"
    assert processor.get_file_type("note.m4a") == "audio/mp4"
    assert processor.get_file_type("clip.opus") == "audio/opus"


def test_parse_vision_ocr_text_list_and_string() -> None:
    """Vision OCR parsing handles list-of-blocks and plain string content."""
    list_result = {
        "output": {"choices": [{"message": {"content": [{"type": "text", "text": "Hello "}, {"text": "world"}]}}]}
    }
    assert _parse_vision_ocr_text(list_result) == "Hello world"

    str_result = {"output": {"choices": [{"message": {"content": "  plain text  "}}]}}
    assert _parse_vision_ocr_text(str_result) == "plain text"

    assert _parse_vision_ocr_text({}) == ""


def test_collect_transcription_urls() -> None:
    """Only succeeded subtask URLs are collected; the single-result shape works too."""
    fun_asr = {
        "results": [
            {"transcription_url": "https://x/1.json", "subtask_status": "SUCCEEDED"},
            {"transcription_url": "https://x/2.json", "subtask_status": "FAILED"},
        ]
    }
    assert _collect_transcription_urls(fun_asr) == ["https://x/1.json"]

    qwen3 = {"result": {"transcription_url": "https://x/single.json"}}
    assert _collect_transcription_urls(qwen3) == ["https://x/single.json"]


def test_download_transcript_text_joins_paragraphs() -> None:
    """Paragraph-level transcript texts are joined, skipping empties."""

    class _Resp:
        """Minimal httpx-like response."""

        @staticmethod
        def raise_for_status() -> None:
            """No-op status check."""
            return None

        @staticmethod
        def json() -> dict:
            """Return a canned transcripts payload."""
            return {"transcripts": [{"text": "first para"}, {"text": "second para"}, {"text": ""}]}

    class _Client:
        """Minimal httpx-like client returning a canned response."""

        @staticmethod
        def get(_url: str) -> "_Resp":
            """Return the canned response."""
            return _Resp()

    text = _download_transcript_text(cast(Any, _Client()), "https://x/result.json")
    assert text == "first para\nsecond para"


def test_audio_hosting_publish_resolve_revoke(monkeypatch) -> None:
    """Publishing mints a token URL; resolve returns the path; revoke clears it."""
    store: dict[str, str] = {}

    class _FakeRedis:
        """In-memory stand-in for the sync Redis client."""

        @staticmethod
        def setex(key: str, _ttl: int, value: str) -> None:
            """Store a value under a key."""
            store[key] = value

        @staticmethod
        def get(key: str):
            """Return the stored value as bytes, or None."""
            value = store.get(key)
            return value.encode("utf-8") if value is not None else None

        @staticmethod
        def delete(key: str) -> None:
            """Remove a key."""
            store.pop(key, None)

    monkeypatch.setattr(audio_hosting, "get_redis", _FakeRedis)
    monkeypatch.setattr(audio_hosting, "config", SimpleNamespace(KNOWLEDGE_AUDIO_PUBLIC_BASE="https://app.example.com"))

    token, url = audio_hosting.publish_audio("/tmp/lecture.mp3")
    assert url == f"https://app.example.com/api/knowledge-space/audio-fetch/{token}"
    assert audio_hosting.resolve_audio_path(token) == "/tmp/lecture.mp3"

    audio_hosting.revoke_audio(token)
    assert audio_hosting.resolve_audio_path(token) is None


def test_audio_hosting_publish_raises_without_redis(monkeypatch) -> None:
    """Publishing fails loudly when Redis is unavailable."""
    monkeypatch.setattr(audio_hosting, "get_redis", lambda: None)
    with pytest.raises(RuntimeError):
        audio_hosting.publish_audio("/tmp/x.mp3")
