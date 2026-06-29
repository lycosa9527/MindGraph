"""Tests for download_runner dispatch."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from unittest.mock import patch

import pytest

try:
    import yt_dlp as _yt_dlp_mod
except ImportError:
    _yt_dlp_mod = None

from file_reader.platform_browser.download_runner import (
    _media_file_extension,
    download_detected_assets,
)
from file_reader.platform_browser.models import DetectedAsset, ProbeContext
from file_reader.wechat_channels.models import CapturedChannelVideo


def test_media_file_extension() -> None:
    """Tencent media URLs map to mp4 or m3u8 extensions."""
    assert _media_file_extension("https://example.com/a.mp4?sig=1") == ".mp4"
    assert _media_file_extension("https://example.com/a.m3u8?sig=1") == ".m3u8"


def test_download_channels_requires_decode_key() -> None:
    """Channels downloads reject captures without decrypt metadata."""
    video = CapturedChannelVideo(
        video_id="abc",
        title="demo",
        media_url="https://finder.video.qq.com/stodownload?encfilekey=abc",
        decode_key="",
    )
    asset = DetectedAsset(
        asset_id="abc",
        title="demo",
        format_label="MP4",
        platform_id="wechat_channels",
        extractor="channels",
        meta={"channels_video": video},
    )
    context = ProbeContext(
        page_url="https://channels.weixin.qq.com/web/pages/feed",
        login_state={},
        cookies=[],
        smartedu_token="",
    )
    saved, errors = download_detected_assets([asset], context)
    assert not saved
    assert len(errors) == 1
    assert "metadata incomplete" in errors[0]


def test_download_ytdlp_delegates_to_extractor() -> None:
    """yt-dlp assets route through download_ytdlp_asset."""
    asset = DetectedAsset(
        asset_id="vid:137",
        title="demo",
        format_label="720p MP4",
        platform_id="bilibili",
        extractor="ytdlp",
        meta={"page_url": "https://www.bilibili.com/video/BV1xx411c7mD", "format_id": "137"},
    )
    context = ProbeContext(
        page_url="https://www.bilibili.com/video/BV1xx411c7mD",
        login_state={},
        cookies=[],
        smartedu_token="",
    )
    expected = Path("/tmp/demo.mp4")
    with patch(
        "file_reader.platform_browser.download_runner.download_ytdlp_asset",
        return_value=expected,
    ) as mocked:
        saved, errors = download_detected_assets([asset], context)
    mocked.assert_called_once()
    assert saved == [expected]
    assert not errors


def test_download_ytdlp_maps_download_error_to_message() -> None:
    """yt-dlp DownloadError is surfaced as a user-facing error string."""
    if _yt_dlp_mod is None:
        pytest.skip("yt_dlp not installed")

    asset = DetectedAsset(
        asset_id="vid:137",
        title="demo",
        format_label="720p MP4",
        platform_id="bilibili",
        extractor="ytdlp",
        meta={"page_url": "https://www.bilibili.com/video/BV1xx411c7mD", "format_id": "137"},
    )
    context = ProbeContext(
        page_url="https://www.bilibili.com/video/BV1xx411c7mD",
        login_state={},
        cookies=[],
        smartedu_token="",
    )
    with patch(
        "file_reader.platform_browser.download_runner.download_ytdlp_asset",
        side_effect=_yt_dlp_mod.utils.DownloadError("blocked"),
    ):
        saved, errors = download_detected_assets([asset], context)
    assert not saved
    assert errors == ["demo: blocked"]


def test_download_cancel_rolls_back_saved_files(tmp_path) -> None:
    """Cancelled batches remove files written before cancellation."""
    cancel_event = Event()
    asset = DetectedAsset(
        asset_id="a1",
        title="first",
        format_label="MP4",
        platform_id="tencent_meeting",
        extractor="media",
        meta={"media_url": "https://example.com/a.mp4"},
    )
    asset_two = DetectedAsset(
        asset_id="a2",
        title="second",
        format_label="MP4",
        platform_id="tencent_meeting",
        extractor="media",
        meta={"media_url": "https://example.com/b.mp4"},
    )
    context = ProbeContext(
        page_url="https://meeting.tencent.com/user-center/shared-record-info",
        login_state={"tencent_meeting_logged_in": True},
        cookies=[],
        smartedu_token="",
        download_folder=tmp_path,
    )
    first_path = tmp_path / "first.mp4"

    def fake_download_one(asset: DetectedAsset, folder: Path, _context: ProbeContext) -> Path:
        if asset.asset_id == "a1":
            first_path.write_bytes(b"demo")
            cancel_event.set()
            return first_path
        return folder / "second.mp4"

    with patch(
        "file_reader.platform_browser.download_runner._download_one",
        side_effect=fake_download_one,
    ):
        saved, errors = download_detected_assets(
            [asset, asset_two],
            context,
            cancel_event=cancel_event,
        )
    assert not saved
    assert any("cancelled" in error.lower() for error in errors)
    assert not first_path.exists()
