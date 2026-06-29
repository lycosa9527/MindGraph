"""Tests for platform site detection and status formatting."""

from __future__ import annotations

from file_reader.i18n import I18n
from file_reader.platform_browser.sites import (
    detect_platform,
    download_auth_ready,
    format_status_line,
    platform_logged_in,
)


def test_detect_platform_smartedu() -> None:
    """SmartEdu hosts map to the smartedu platform."""
    site = detect_platform("https://basic.smartedu.cn/syncClassroom/classActivity?activityId=x")
    assert site.site_id == "smartedu"


def test_detect_platform_bilibili() -> None:
    """Bilibili watch URLs map to bilibili."""
    site = detect_platform("https://www.bilibili.com/video/BV1xx411c7mD")
    assert site.site_id == "bilibili"


def test_detect_platform_douyin() -> None:
    """Douyin watch URLs map to douyin."""
    site = detect_platform("https://www.douyin.com/video/7505453424973024549")
    assert site.site_id == "douyin"


def test_detect_platform_tiktok() -> None:
    """TikTok watch URLs map to tiktok."""
    site = detect_platform("https://www.tiktok.com/@user/video/123")
    assert site.site_id == "tiktok"


def test_detect_platform_wechat_channels() -> None:
    """WeChat Channels pages map to wechat_channels."""
    site = detect_platform("https://channels.weixin.qq.com/web/pages/feed")
    assert site.site_id == "wechat_channels"


def test_detect_platform_youtube() -> None:
    """YouTube watch URLs map to youtube."""
    site = detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert site.site_id == "youtube"


def test_format_status_line_smartedu_zh() -> None:
    """Status line shows one platform only."""
    i18n = I18n("zh")
    site = detect_platform("https://basic.smartedu.cn/")
    line = format_status_line(
        i18n,
        site,
        {"smartedu_logged_in": True},
        smartedu_token="abc",
        page_url="https://basic.smartedu.cn/",
    )
    assert line.startswith("国家智慧教育平台：已登录")
    assert "令牌已保存" in line


def test_download_auth_ready_smartedu_requires_token() -> None:
    """SmartEdu downloads require a saved token."""
    site = detect_platform("https://basic.smartedu.cn/tchMaterial/detail?contentId=x")
    assert download_auth_ready(site, {}, smartedu_token="", asset_count=2) is False
    assert download_auth_ready(site, {}, smartedu_token="tok", asset_count=2) is True


def test_download_auth_ready_bilibili_without_token() -> None:
    """Bilibili allows download probe results without SmartEdu token."""
    site = detect_platform("https://www.bilibili.com/video/BV1xx411c7mD")
    assert download_auth_ready(site, {}, smartedu_token="", asset_count=1) is True


def test_platform_logged_in_bilibili_cookie() -> None:
    """Bilibili login flag comes from login state."""
    site = detect_platform("https://www.bilibili.com/")
    assert platform_logged_in(site, {"bilibili_logged_in": True}) is True


def test_platform_logged_in_smartedu_saved_token() -> None:
    """Saved SmartEdu token counts as signed in for status."""
    site = detect_platform("https://basic.smartedu.cn/")
    assert platform_logged_in(site, {}, smartedu_token="saved-token") is True


def test_format_status_line_smartedu_token_without_page_login() -> None:
    """Status shows signed in when only a saved token exists."""
    i18n = I18n("zh")
    site = detect_platform("https://basic.smartedu.cn/")
    line = format_status_line(
        i18n,
        site,
        {},
        smartedu_token="abc",
        page_url="https://basic.smartedu.cn/",
    )
    assert "已登录" in line
    assert "令牌已保存" in line


def test_format_status_line_download_ready() -> None:
    """Download-ready pages show a dedicated status instead of login state."""
    i18n = I18n("zh")
    site = detect_platform("https://www.bilibili.com/video/BV1xx411c7mD")
    line = format_status_line(
        i18n,
        site,
        {},
        smartedu_token="",
        page_url="https://www.bilibili.com/video/BV1xx411c7mD",
        download_ready=True,
    )
    assert line.startswith("哔哩哔哩：可下载")
