"""Tests for platform asset registry routing."""

from __future__ import annotations

from unittest.mock import patch

from file_reader.platform_browser.models import DetectedAsset, ProbeContext
from file_reader.platform_browser.registry import probe_assets
from file_reader.smartedu.models import SmartEduAsset, SmartEduLesson
from file_reader.wechat_channels.models import CapturedChannelVideo


def test_probe_smartedu_lesson_assets() -> None:
    """SmartEdu URLs route to lesson CDN probe."""
    lesson = SmartEduLesson(
        lesson_id="id",
        title="Demo",
        detail_url="https://example.com/detail.json",
        assets=[
            SmartEduAsset(
                asset_id="a1",
                title="Video",
                alias="video",
                resource_type="micro_lesson_video",
                format="mp4",
                download_url="https://example.com/a.m3u8",
            ),
        ],
    )
    context = ProbeContext(
        page_url=(
            "https://basic.smartedu.cn/syncClassroom/classActivity?activityId=b45c766e-1234-5678-9abc-def012345678"
        ),
        login_state={"smartedu_logged_in": True},
        cookies=[],
        smartedu_token="token",
    )
    with patch("file_reader.platform_browser.smartedu_extractor.smartedu_metadata.fetch_lesson", return_value=lesson):
        result = probe_assets(context)
    assert len(result.assets) == 1
    assert result.download_enabled is True


def test_probe_unknown_host_returns_empty() -> None:
    """Unknown hosts do not run extractors."""
    context = ProbeContext(
        page_url="https://example.com/page",
        login_state={},
        cookies=[],
        smartedu_token="",
    )
    result = probe_assets(context)
    assert not result.assets
    assert result.download_enabled is False


def test_probe_bilibili_routes_to_ytdlp() -> None:
    """Bilibili URLs use the yt-dlp probe."""
    asset = DetectedAsset(
        asset_id="vid:137",
        title="demo",
        format_label="720p MP4",
        platform_id="bilibili",
        extractor="ytdlp",
        meta={"group_id": "vid"},
    )
    context = ProbeContext(
        page_url="https://www.bilibili.com/video/BV1xx411c7mD",
        login_state={},
        cookies=[],
        smartedu_token="",
    )
    with patch(
        "file_reader.platform_browser.registry.probe_ytdlp_assets",
        return_value=(asset,),
    ) as mocked:
        result = probe_assets(context)
    mocked.assert_called_once_with(context)
    assert result.download_enabled is True
    assert result.badge_count == 1


def test_probe_channels_play_hint() -> None:
    """Channels pages without captures show a play hint."""
    context = ProbeContext(
        page_url="https://channels.weixin.qq.com/web/pages/feed",
        login_state={},
        cookies=[],
        smartedu_token="",
    )
    result = probe_assets(context)
    assert not result.assets
    assert result.status_hint == "channels_play_needed"


def test_probe_channels_with_capture() -> None:
    """Channels captures become downloadable assets."""
    video = CapturedChannelVideo(
        video_id="abc",
        title="demo",
        media_url="https://finder.video.qq.com/stodownload?encfilekey=abc",
        decode_key="123",
    )
    context = ProbeContext(
        page_url="https://channels.weixin.qq.com/web/pages/feed",
        login_state={},
        cookies=[],
        smartedu_token="",
        captured_channels_videos=(video,),
    )
    result = probe_assets(context)
    assert len(result.assets) == 1
    assert result.download_enabled is True
