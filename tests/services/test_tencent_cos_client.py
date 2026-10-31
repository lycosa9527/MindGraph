"""Tests for Tencent COS client helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from services.utils import tencent_cos_client


def test_cos_object_key_normalizes_prefix():
    with patch.object(tencent_cos_client, "COS_KEY_PREFIX", "backups/test"):
        key = tencent_cos_client.cos_object_key("sync/crowdsec/blocklist.txt")
        assert key == "backups/test/sync/crowdsec/blocklist.txt"


def test_sha256_hex():
    digest = tencent_cos_client.sha256_hex(b"hello")
    assert len(digest) == 64


def test_cos_bucket_configured_rejects_env_example_placeholder():
    assert tencent_cos_client.cos_bucket_configured("mindgraph-1356113246") is True
    assert tencent_cos_client.cos_bucket_configured("your-bucket-name-appid") is False
    assert tencent_cos_client.cos_bucket_configured("") is False


def test_cos_credentials_configured_ignores_placeholder_bucket():
    with (
        patch.object(tencent_cos_client, "COS_SECRET_ID", "AKID"),
        patch.object(tencent_cos_client, "COS_SECRET_KEY", "secret"),
        patch.object(tencent_cos_client, "COS_REGION", "ap-beijing"),
        patch.object(tencent_cos_client, "COS_BUCKET", "your-bucket-name-appid"),
    ):
        assert tencent_cos_client.cos_credentials_configured() is False


def test_upload_file_delegates_to_client(tmp_path: Path):
    local = tmp_path / "sample.dump"
    local.write_bytes(b"data")
    mock_client = MagicMock()
    mock_client.upload_file.return_value = {"ETag": "abc"}
    with patch.object(tencent_cos_client, "get_cos_client", return_value=mock_client):
        with patch.object(tencent_cos_client, "cos_credentials_configured", return_value=True):
            with patch.object(tencent_cos_client, "COS_BUCKET", "bucket"):
                ok = tencent_cos_client.upload_file(local, "backups/test/sample.dump")
    assert ok is True
    mock_client.upload_file.assert_called_once()
