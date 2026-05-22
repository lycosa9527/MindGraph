"""Unit tests for per-organization MindMate avatar processing."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

from routers.auth.admin import organization_mindmate_branding as branding


def _jpeg_bytes(width: int, height: int, color: str = "red") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="JPEG")
    return buffer.getvalue()


def _png_bytes(width: int, height: int, color: str = "blue") -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", (width, height), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _animated_gif_bytes(
    frame_size: tuple[int, int],
    frame_count: int,
    *,
    duration_ms: int = 100,
) -> bytes:
    buffer = BytesIO()
    width, height = frame_size
    palette = ("red", "green", "blue", "yellow", "purple", "orange")
    frames = [
        Image.new("RGBA", (width, height), palette[index % len(palette)])
        for index in range(frame_count)
    ]
    first, *rest = frames
    first.save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=rest,
        loop=0,
        duration=duration_ms,
    )
    return buffer.getvalue()


def _upload_file(contents: bytes, *, content_type: str = "image/png") -> UploadFile:
    return UploadFile(
        filename="avatar.bin",
        file=BytesIO(contents),
        headers={"content-type": content_type},
    )


@pytest.fixture(name="isolated_avatar_storage")
def isolated_avatar_storage_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    storage_root = tmp_path / "org_mindmate_avatars"
    monkeypatch.setattr(branding, "ORG_MINDMATE_AVATARS_DIR", storage_root)
    return storage_root


def test_process_static_avatar_landscape_jpeg() -> None:
    contents = _jpeg_bytes(400, 200)
    with Image.open(BytesIO(contents)) as opened:
        processed = branding._process_static_avatar_image(opened)

    assert processed.size == (branding.MINDMATE_AVATAR_OUTPUT_PX, branding.MINDMATE_AVATAR_OUTPUT_PX)


def test_process_static_avatar_portrait_png() -> None:
    contents = _png_bytes(180, 320)
    with Image.open(BytesIO(contents)) as opened:
        processed = branding._process_static_avatar_image(opened)

    assert processed.size == (branding.MINDMATE_AVATAR_OUTPUT_PX, branding.MINDMATE_AVATAR_OUTPUT_PX)


def test_process_static_avatar_rejects_tiny_image() -> None:
    contents = _png_bytes(32, 32)
    with Image.open(BytesIO(contents)) as opened:
        with pytest.raises(HTTPException) as exc_info:
            branding._process_static_avatar_image(opened)

    assert exc_info.value.detail == "mindmate_avatar_too_small"


def test_process_animated_gif_preserves_frames() -> None:
    contents = _animated_gif_bytes((200, 100), 3)
    with Image.open(BytesIO(contents)) as opened:
        frames, durations = branding._process_animated_gif_avatar(opened)

    assert len(frames) == 3
    assert len(durations) == 3
    assert all(frame.size == (256, 256) for frame in frames)


def test_process_animated_gif_rejects_too_many_frames() -> None:
    contents = _animated_gif_bytes((120, 120), branding.MAX_GIF_FRAMES + 1)
    with Image.open(BytesIO(contents)) as opened:
        with pytest.raises(HTTPException) as exc_info:
            branding._process_animated_gif_avatar(opened)

    assert exc_info.value.detail == "mindmate_avatar_gif_too_many_frames"


@pytest.mark.asyncio
async def test_save_mindmate_agent_avatar_rejects_invalid_bytes(
    isolated_avatar_storage: Path,
) -> None:
    org = SimpleNamespace(id=7, mindmate_agent_avatar_url=None)
    upload = _upload_file(b"not-an-image", content_type="image/png")

    with pytest.raises(HTTPException) as exc_info:
        await branding.save_mindmate_agent_avatar(org, upload)

    assert exc_info.value.detail == "mindmate_avatar_invalid_image"
    assert not (isolated_avatar_storage / "7").exists()


@pytest.mark.asyncio
async def test_save_mindmate_agent_avatar_rejects_oversized_dimensions(
    isolated_avatar_storage: Path,
) -> None:
    org = SimpleNamespace(id=9, mindmate_agent_avatar_url=None)
    upload = _upload_file(
        _png_bytes(branding.MAX_AVATAR_DECODE_PX + 1, 128),
        content_type="image/png",
    )

    with pytest.raises(HTTPException) as exc_info:
        await branding.save_mindmate_agent_avatar(org, upload)

    assert exc_info.value.detail == "mindmate_avatar_invalid_image"
    assert not (isolated_avatar_storage / "9").exists()


@pytest.mark.asyncio
async def test_save_mindmate_agent_avatar_writes_png_with_cache_bust(
    isolated_avatar_storage: Path,
) -> None:
    org = SimpleNamespace(id=11, mindmate_agent_avatar_url=None)
    upload = _upload_file(_jpeg_bytes(300, 300), content_type="image/jpeg")

    url = await branding.save_mindmate_agent_avatar(org, upload)

    assert url.startswith("/static/org_mindmate_avatars/11/avatar.png?v=")
    png_path = isolated_avatar_storage / "11" / branding.ORG_AVATAR_PNG_FILENAME
    assert png_path.is_file()
    with Image.open(png_path) as saved:
        assert saved.size == (256, 256)


@pytest.mark.asyncio
async def test_save_mindmate_agent_avatar_writes_animated_gif(
    isolated_avatar_storage: Path,
) -> None:
    org = SimpleNamespace(id=12, mindmate_agent_avatar_url=None)
    upload = _upload_file(_animated_gif_bytes((160, 160), 2), content_type="image/gif")

    url = await branding.save_mindmate_agent_avatar(org, upload)

    assert url.startswith("/static/org_mindmate_avatars/12/avatar.gif?v=")
    gif_path = isolated_avatar_storage / "12" / branding.ORG_AVATAR_GIF_FILENAME
    assert gif_path.is_file()
    with Image.open(gif_path) as saved:
        assert getattr(saved, "n_frames", 1) == 2
        saved.seek(0)
        assert saved.size == (256, 256)


@pytest.mark.asyncio
async def test_save_mindmate_agent_avatar_keeps_old_file_until_finalize(
    isolated_avatar_storage: Path,
) -> None:
    org = SimpleNamespace(id=13, mindmate_agent_avatar_url=None)
    png_upload = _upload_file(_png_bytes(128, 128), content_type="image/png")
    org.mindmate_agent_avatar_url = await branding.save_mindmate_agent_avatar(org, png_upload)

    gif_upload = _upload_file(_animated_gif_bytes((128, 128), 2), content_type="image/gif")
    new_url = await branding.save_mindmate_agent_avatar(org, gif_upload)

    org_dir = isolated_avatar_storage / "13"
    assert (org_dir / branding.ORG_AVATAR_PNG_FILENAME).is_file()
    assert (org_dir / branding.ORG_AVATAR_GIF_FILENAME).is_file()

    branding.finalize_mindmate_avatar_upload(13, org.mindmate_agent_avatar_url, new_url)

    assert not (org_dir / branding.ORG_AVATAR_PNG_FILENAME).exists()
    assert (org_dir / branding.ORG_AVATAR_GIF_FILENAME).is_file()


def test_revert_mindmate_avatar_upload_removes_new_file_but_keeps_replaced_file(
    isolated_avatar_storage: Path,
) -> None:
    org_dir = isolated_avatar_storage / "21"
    org_dir.mkdir(parents=True)
    png_path = org_dir / branding.ORG_AVATAR_PNG_FILENAME
    png_path.write_bytes(_png_bytes(128, 128))

    old_url = branding.mindmate_org_avatar_public_url(21, animated=False) + "?v=1"
    new_url = branding.mindmate_org_avatar_public_url(21, animated=False) + "?v=2"
    png_path.write_bytes(_png_bytes(256, 256, color="green"))

    branding.revert_mindmate_avatar_upload(old_url, new_url)

    assert png_path.is_file()


def test_revert_mindmate_avatar_upload_removes_new_format_file(
    isolated_avatar_storage: Path,
) -> None:
    org_dir = isolated_avatar_storage / "22"
    org_dir.mkdir(parents=True)
    (org_dir / branding.ORG_AVATAR_PNG_FILENAME).write_bytes(_png_bytes(128, 128))
    (org_dir / branding.ORG_AVATAR_GIF_FILENAME).write_bytes(_animated_gif_bytes((128, 128), 2))

    old_url = branding.mindmate_org_avatar_public_url(22, animated=False) + "?v=1"
    new_url = branding.mindmate_org_avatar_public_url(22, animated=True) + "?v=2"

    branding.revert_mindmate_avatar_upload(old_url, new_url)

    assert (org_dir / branding.ORG_AVATAR_PNG_FILENAME).is_file()
    assert not (org_dir / branding.ORG_AVATAR_GIF_FILENAME).exists()


def test_local_mindmate_avatar_path_strips_cache_buster_for_png() -> None:
    canonical = branding.mindmate_org_avatar_public_url(5, animated=False)
    resolved = branding.local_mindmate_avatar_path(f"{canonical}?v=123456")
    expected = (branding.ORG_MINDMATE_AVATARS_DIR / "5" / branding.ORG_AVATAR_PNG_FILENAME).resolve()

    assert resolved == expected


def test_local_mindmate_avatar_path_strips_cache_buster_for_gif() -> None:
    canonical = branding.mindmate_org_avatar_public_url(8, animated=True)
    resolved = branding.local_mindmate_avatar_path(f"{canonical}?v=987654")
    expected = (branding.ORG_MINDMATE_AVATARS_DIR / "8" / branding.ORG_AVATAR_GIF_FILENAME).resolve()

    assert resolved == expected


def test_local_mindmate_avatar_path_rejects_non_canonical_paths() -> None:
    assert branding.local_mindmate_avatar_path("/static/org_mindmate_avatars/5/evil.png") is None
    assert branding.local_mindmate_avatar_path("/static/org_mindmate_avatars/../secrets") is None
    assert (
        branding.local_mindmate_avatar_path("/static/org_mindmate_avatars/5/avatar.jpg?v=1")
        is None
    )


def test_cleanup_stale_upload_temps_removes_orphan_files(
    isolated_avatar_storage: Path,
) -> None:
    org_dir = isolated_avatar_storage / "31"
    org_dir.mkdir(parents=True)
    stale = org_dir / ".upload-deadbeef.avatar.png"
    stale.write_bytes(_png_bytes(64, 64))
    keep = org_dir / branding.ORG_AVATAR_PNG_FILENAME
    keep.write_bytes(_png_bytes(64, 64))

    branding._cleanup_stale_upload_temps(org_dir)

    assert not stale.exists()
    assert keep.is_file()
