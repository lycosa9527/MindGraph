"""generate_dingtalk preview PNG local cache + COS hydrate."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.diagram import temp_image_storage as storage


def test_is_safe_dingtalk_temp_filename() -> None:
    """Accept only generate_dingtalk PNG names with no path."""
    assert storage.is_safe_dingtalk_temp_filename("dingtalk_deadbeef_1710000000.png")
    assert not storage.is_safe_dingtalk_temp_filename("dingtalk_deadbeef_1710000000.png/../x")
    assert not storage.is_safe_dingtalk_temp_filename("diagram_abc.png")
    assert not storage.is_safe_dingtalk_temp_filename("")


def test_temp_images_signed_ttl_local_when_cos_off() -> None:
    """Local-only deployments keep the 24h signed URL window."""
    with patch.object(storage, "cos_temp_images_enabled", return_value=False):
        assert storage.temp_images_signed_ttl() == storage.LOCAL_SIGNED_TTL_SECONDS


def test_temp_images_signed_ttl_uses_config_when_cos_on() -> None:
    """COS-backed previews use the configured long-lived URL TTL."""
    fake_config = MagicMock()
    fake_config.COS_TEMP_IMAGES_URL_TTL_SECONDS = 315360000
    with (
        patch.object(storage, "cos_temp_images_enabled", return_value=True),
        patch.object(storage, "config", fake_config),
    ):
        assert storage.temp_images_signed_ttl() == 315360000


@pytest.mark.asyncio
async def test_persist_writes_local_and_uploads_when_cos_on(tmp_path: Path) -> None:
    """Persist writes the local cache and mirrors bytes to COS."""
    filename = "dingtalk_deadbeef_1710000000.png"
    with (
        patch.object(storage, "temp_images_dir", return_value=tmp_path),
        patch.object(storage, "cos_temp_images_enabled", return_value=True),
        patch.object(storage, "dingtalk_temp_cos_key", return_value="pref/dingtalk/x.png"),
        patch.object(storage, "upload_bytes", return_value=True) as upload,
    ):
        path = await storage.persist_dingtalk_temp_png(filename, b"\x89PNG")
    assert path.read_bytes() == b"\x89PNG"
    upload.assert_called_once()


@pytest.mark.asyncio
async def test_persist_keeps_local_when_cos_upload_fails(tmp_path: Path) -> None:
    """COS upload failure must not delete the local PNG."""
    filename = "dingtalk_deadbeef_1710000000.png"
    with (
        patch.object(storage, "temp_images_dir", return_value=tmp_path),
        patch.object(storage, "cos_temp_images_enabled", return_value=True),
        patch.object(storage, "dingtalk_temp_cos_key", return_value="pref/dingtalk/x.png"),
        patch.object(storage, "upload_bytes", return_value=False),
    ):
        path = await storage.persist_dingtalk_temp_png(filename, b"png")
    assert path.is_file()


@pytest.mark.asyncio
async def test_hydrate_returns_local_without_cos(tmp_path: Path) -> None:
    """Existing local files are served without a COS download."""
    filename = "dingtalk_deadbeef_1710000000.png"
    (tmp_path / filename).write_bytes(b"png")
    with (
        patch.object(storage, "temp_images_dir", return_value=tmp_path),
        patch.object(storage, "cos_temp_images_enabled", return_value=False),
        patch.object(storage, "download_file") as download,
    ):
        path = await storage.hydrate_dingtalk_temp_png(filename)
    assert path == tmp_path / filename
    download.assert_not_called()


@pytest.mark.asyncio
async def test_hydrate_pulls_from_cos_when_local_missing(tmp_path: Path) -> None:
    """Missing local cache is restored from COS."""
    filename = "dingtalk_deadbeef_1710000000.png"

    def _download(_key: str, dest: Path, **_kwargs: object) -> bool:
        dest.write_bytes(b"from-cos")
        return True

    with (
        patch.object(storage, "temp_images_dir", return_value=tmp_path),
        patch.object(storage, "cos_temp_images_enabled", return_value=True),
        patch.object(storage, "dingtalk_temp_cos_key", return_value="pref/dingtalk/x.png"),
        patch.object(storage, "download_file", side_effect=_download),
    ):
        path = await storage.hydrate_dingtalk_temp_png(filename)
    assert path is not None
    assert path.read_bytes() == b"from-cos"


@pytest.mark.asyncio
async def test_hydrate_rejects_unsafe_filename(tmp_path: Path) -> None:
    """Path-like names must not hydrate."""
    with patch.object(storage, "temp_images_dir", return_value=tmp_path):
        assert await storage.hydrate_dingtalk_temp_png("../secret.png") is None
