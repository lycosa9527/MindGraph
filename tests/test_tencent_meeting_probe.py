"""Tests for Tencent Meeting media URL parsing."""

from __future__ import annotations

from file_reader.platform_browser.media_extractor import probe_media_assets
from file_reader.platform_browser.models import ProbeContext
from file_reader.tencent_meeting.url_parser import is_recording_page, is_tencent_media_url, parse_media_urls


def test_is_recording_page() -> None:
    """Tencent Meeting host is recognized."""
    assert is_recording_page("https://meeting.tencent.com/v2/cloud-record/share?id=abc")


def test_is_tencent_media_url() -> None:
    """Tencent cloud recording URLs are recognized from network captures."""
    assert is_tencent_media_url("https://yunluzhi.file.myqcloud.com/recording.mp4?sign=1")
    assert is_tencent_media_url("https://example.com/page.html") is False


def test_parse_media_urls_from_json_list() -> None:
    """Probe JS JSON output is parsed."""
    raw = '["https://yunluzhi.file.myqcloud.com/recording.mp4?sign=1"]'
    urls = parse_media_urls(raw)
    assert len(urls) == 1
    assert urls[0].endswith("recording.mp4?sign=1")


def test_probe_media_assets_on_meeting_page() -> None:
    """Captured media URLs become detected assets."""
    context = ProbeContext(
        page_url="https://meeting.tencent.com/v2/cloud-record/share?id=abc",
        login_state={"tencent_meeting_logged_in": True},
        cookies=[],
        smartedu_token="",
        captured_media_urls=("https://yunluzhi.file.myqcloud.com/a.mp4",),
    )
    assets = probe_media_assets(context)
    assert len(assets) == 1
    assert assets[0].platform_id == "tencent_meeting"
