"""Clip decks stay on disk in development and go to COS on test and production."""

from __future__ import annotations

import pytest

from config.settings import config
from services.features.clip_lessons import storage

_LESSON = "550e8400-e29b-41d4-a716-446655440000"
_KEY = f"clip-lessons/{_LESSON}/deck.pptx"


def _clear_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COS_ENV_PREFIX", raising=False)
    monkeypatch.delenv("COS_CLIP_TEACHING_PREFIX", raising=False)
    config.refresh_env_cache()


def test_development_video_stays_on_disk(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A development clip is a local file, not a Tencent upload."""
    _clear_prefix(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setattr(storage, "_ROOT", tmp_path / "clip-lessons")
    key = storage.lesson_video_key(_LESSON, ".mp4")
    try:
        storage.write_local_video(key, b"video-bytes")
        assert storage.local_video_file(key).read_bytes() == b"video-bytes"
        assert storage.video_media_type(key) == "video/mp4"
        storage.write_local_video(storage.lesson_video_key(_LESSON, ".webm"), b"webm")
        assert not storage.local_video_file(key).exists()
    finally:
        config.refresh_env_cache()


def test_development_writes_local_disk(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A development machine does not upload, even when COS credentials exist."""
    _clear_prefix(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setattr(storage, "_ROOT", tmp_path / "clip-lessons")

    def _reject_upload(*_args, **_kwargs) -> bool:
        raise AssertionError("development must not upload clip decks")

    monkeypatch.setattr(storage, "upload_bytes", _reject_upload)
    try:
        storage.put_object(_KEY, b"pptx-bytes", "application/vnd.ms-powerpoint")
        assert storage.read_object(_KEY) == b"pptx-bytes"
        storage.delete_object_key(_KEY)
        assert storage.read_object(_KEY) is None
    finally:
        config.refresh_env_cache()


def test_test_host_uploads_under_test_prefix(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The test machine sends the deck to test/clip-teaching and skips local disk."""
    _clear_prefix(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "test")
    config.refresh_env_cache()
    monkeypatch.setattr(storage, "_ROOT", tmp_path / "clip-lessons")
    monkeypatch.setattr(storage, "cos_credentials_configured", lambda: True)
    captured: dict[str, object] = {}

    def _upload(data: bytes, key: str, **_kwargs) -> bool:
        captured["data"] = data
        captured["key"] = key
        return True

    monkeypatch.setattr(storage, "upload_bytes", _upload)
    try:
        storage.put_object(_KEY, b"pptx-bytes", "application/vnd.ms-powerpoint")
        assert captured["key"] == f"test/clip-teaching/{_KEY}"
        assert captured["data"] == b"pptx-bytes"
        assert not (tmp_path / "clip-lessons").exists()
    finally:
        config.refresh_env_cache()


def test_production_uploads_under_live_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production keeps the live clip-teaching/mindgraph prefix."""
    _clear_prefix(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    config.refresh_env_cache()
    monkeypatch.setattr(storage, "cos_credentials_configured", lambda: True)
    captured: dict[str, str] = {}

    def _upload(_data: bytes, key: str, **_kwargs) -> bool:
        captured["key"] = key
        return True

    monkeypatch.setattr(storage, "upload_bytes", _upload)
    try:
        storage.put_object(_KEY, b"pptx-bytes", "application/pdf")
    finally:
        config.refresh_env_cache()
    assert captured["key"] == f"clip-teaching/mindgraph/{_KEY}"
