"""Tests for WeChat Channels asset probe."""

from __future__ import annotations

from file_reader.platform_browser.channels_extractor import probe_channels_assets
from file_reader.platform_browser.models import ProbeContext
from file_reader.wechat_channels.models import CapturedChannelVideo


def test_probe_channels_skips_network_only_capture() -> None:
    """Network-only captures without decode_key are not downloadable yet."""
    video = CapturedChannelVideo(
        video_id="abc",
        title="demo",
        media_url="https://finder.video.qq.com/251/20302/stodownload?encfilekey=abc",
        decode_key="",
    )
    context = ProbeContext(
        page_url="https://channels.weixin.qq.com/web/pages/feed",
        login_state={},
        cookies=[],
        smartedu_token="",
        captured_channels_videos=(video,),
    )
    assets = probe_channels_assets(context)
    assert not assets


def test_probe_channels_includes_hook_capture() -> None:
    """Hook captures with decode_key become downloadable assets."""
    video = CapturedChannelVideo(
        video_id="abc",
        title="demo",
        media_url="https://finder.video.qq.com/251/20302/stodownload?encfilekey=abc",
        decode_key="123",
    )
    context = ProbeContext(
        page_url="https://channels.weixin.qq.com/web/pages/feed",
        login_state={},
        cookies=[],
        smartedu_token="",
        captured_channels_videos=(video,),
    )
    assets = probe_channels_assets(context)
    assert len(assets) == 1
    assert assets[0].extractor == "channels"
