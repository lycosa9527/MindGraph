"""Workshop attachment COS/local storage helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from config.cos_env_prefix import cos_feature_prefix
from config.settings import config
from services.features.workshop_chat.attachment_storage import (
    STORAGE_LOCAL,
    assert_safe_logical_key,
    build_logical_key,
    cos_workshop_enabled,
    full_workshop_cos_key,
    is_legacy_disk_path,
    local_path_for_key,
    put_attachment_bytes_sync,
    resolve_stored_payload_sync,
    storage_backend,
)


def test_logical_key_has_no_cos_host() -> None:
    """Persisted keys are relative paths, not durable COS URLs."""
    key = build_logical_key("notes.pdf")
    assert key.endswith("_notes.pdf")
    assert "://" not in key
    assert not key.startswith("/")
    assert ".." not in key


def test_legacy_disk_path_detection() -> None:
    """Pre-COS rows keep the /static/chat/ prefix."""
    assert is_legacy_disk_path("/static/chat/2026/09/ab_notes.pdf") is True
    assert is_legacy_disk_path("2026/09/ab_notes.pdf") is False


def test_safe_logical_key_rejects_traversal() -> None:
    """Relative keys cannot escape the chat prefix."""
    with pytest.raises(ValueError, match="Invalid attachment key"):
        assert_safe_logical_key("../secret.txt")
    with pytest.raises(ValueError, match="Invalid attachment key"):
        assert_safe_logical_key("")


def test_local_path_stays_under_root(tmp_path: Path) -> None:
    """Resolved local paths stay inside the chat static root."""
    path = local_path_for_key("2026/09/ab_notes.pdf", tmp_path)
    assert path == (tmp_path / "2026/09/ab_notes.pdf").resolve()
    with pytest.raises(ValueError, match="Invalid attachment key"):
        local_path_for_key("../../etc/passwd", tmp_path)


def test_workshop_prefix_defaults_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset COS_WORKSHOP_PREFIX follows ENVIRONMENT like training."""
    monkeypatch.delenv("COS_WORKSHOP_PREFIX", raising=False)
    monkeypatch.delenv("COS_ENV_PREFIX", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert cos_feature_prefix("workshop", "") == "dev/workshop"
    monkeypatch.setenv("ENVIRONMENT", "test")
    assert cos_feature_prefix("workshop", "") == "test/workshop"


def test_workshop_config_prefix_follows_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """COS_WORKSHOP_PREFIX defaults from ENVIRONMENT; override still wins."""
    monkeypatch.delenv("COS_WORKSHOP_PREFIX", raising=False)
    monkeypatch.delenv("COS_ENV_PREFIX", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "test")
    config.refresh_env_cache()
    try:
        assert config.COS_WORKSHOP_PREFIX == "test/workshop"
        monkeypatch.setenv("ENVIRONMENT", "development")
        config.refresh_env_cache()
        assert config.COS_WORKSHOP_PREFIX == "dev/workshop"
        monkeypatch.setenv("COS_WORKSHOP_PREFIX", "workshop/mindgraph-e2e-smoke")
        config.refresh_env_cache()
        assert config.COS_WORKSHOP_PREFIX == "workshop/mindgraph-e2e-smoke"
    finally:
        config.refresh_env_cache()


def test_cos_disabled_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """COS stays off when the flag is on but CAM/bucket are missing."""
    monkeypatch.setenv("COS_WORKSHOP_ENABLED", "true")
    with patch(
        "services.features.workshop_chat.attachment_storage.cos_credentials_configured",
        return_value=False,
    ):
        assert cos_workshop_enabled() is False
        assert storage_backend() == STORAGE_LOCAL


def test_local_put_and_resolve(tmp_path: Path) -> None:
    """Local fallback writes bytes and resolves them back to disk."""
    with patch(
        "services.features.workshop_chat.attachment_storage.cos_workshop_enabled",
        return_value=False,
    ):
        stored = put_attachment_bytes_sync(
            "2026/09/ab_notes.txt",
            b"hello",
            "text/plain",
            tmp_path,
        )
        assert stored == "2026/09/ab_notes.txt"
        payload = resolve_stored_payload_sync(
            stored,
            "text/plain",
            "notes.txt",
            tmp_path,
        )
    assert payload is not None
    assert payload.disk_path is not None
    assert payload.disk_path.read_bytes() == b"hello"
    assert payload.redirect_url is None


def test_cos_put_does_not_write_local(tmp_path: Path) -> None:
    """COS uploads skip the app disk so attachments do not stay on the server."""
    with (
        patch(
            "services.features.workshop_chat.attachment_storage.cos_workshop_enabled",
            return_value=True,
        ),
        patch(
            "services.features.workshop_chat.attachment_storage.upload_bytes",
            return_value=True,
        ) as upload,
        patch("services.features.workshop_chat.attachment_storage.config") as mock_config,
    ):
        mock_config.COS_WORKSHOP_PREFIX = "workshop/mindgraph-Dev"
        stored = put_attachment_bytes_sync(
            "2026/09/ab_pic.png",
            b"png-bytes",
            "image/png",
            tmp_path,
        )
    assert stored == "2026/09/ab_pic.png"
    upload.assert_called_once()
    assert not list(tmp_path.rglob("*"))


def test_cos_put_raises_when_upload_fails(tmp_path: Path) -> None:
    """A COS failure must not create a local orphan or a DB-ready key."""
    with (
        patch(
            "services.features.workshop_chat.attachment_storage.cos_workshop_enabled",
            return_value=True,
        ),
        patch(
            "services.features.workshop_chat.attachment_storage.upload_bytes",
            return_value=False,
        ),
        pytest.raises(ValueError, match="COS"),
    ):
        put_attachment_bytes_sync("2026/09/ab_pic.png", b"x", "image/png", tmp_path)


def test_cos_resolve_returns_presigned_redirect(tmp_path: Path) -> None:
    """Downloads 302 to a short-lived COS URL and never expose a durable host in DB."""
    with (
        patch(
            "services.features.workshop_chat.attachment_storage.cos_workshop_enabled",
            return_value=True,
        ),
        patch(
            "services.features.workshop_chat.attachment_storage.generate_presigned_get_url",
            return_value="https://example.myqcloud.com/signed",
        ),
        patch("services.features.workshop_chat.attachment_storage.config") as mock_config,
    ):
        mock_config.COS_WORKSHOP_PREFIX = "workshop/mindgraph"
        mock_config.COS_WORKSHOP_PRESIGN_GET_TTL = 300
        payload = resolve_stored_payload_sync(
            "2026/09/ab_pic.png",
            "image/png",
            "pic.png",
            tmp_path,
        )
    assert payload is not None
    assert payload.redirect_url == "https://example.myqcloud.com/signed"
    assert payload.disk_path is None


def test_legacy_disk_resolve_even_when_cos_on(tmp_path: Path) -> None:
    """Pre-COS rows stay on disk; COS being on must not 302 those keys."""
    relative = "2026/09/ab_legacy.txt"
    disk = tmp_path / relative
    disk.parent.mkdir(parents=True)
    disk.write_bytes(b"legacy")
    with (
        patch(
            "services.features.workshop_chat.attachment_storage.cos_workshop_enabled",
            return_value=True,
        ),
        patch("services.features.workshop_chat.attachment_storage.generate_presigned_get_url") as presign,
    ):
        payload = resolve_stored_payload_sync(
            f"/static/chat/{relative}",
            "text/plain",
            "legacy.txt",
            tmp_path,
        )
    assert payload is not None
    assert payload.disk_path == disk.resolve()
    assert payload.redirect_url is None
    presign.assert_not_called()


def test_full_cos_key_uses_workshop_prefix() -> None:
    """Bucket keys stay under the workshop feature prefix."""
    with patch("services.features.workshop_chat.attachment_storage.config") as mock_config:
        mock_config.COS_WORKSHOP_PREFIX = "workshop/mindgraph-Dev"
        key = full_workshop_cos_key("2026/09/ab_pic.png")
    assert key == "workshop/mindgraph-Dev/2026/09/ab_pic.png"
