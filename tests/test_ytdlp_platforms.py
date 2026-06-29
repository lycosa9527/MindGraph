"""Tests for yt-dlp platform configuration."""

from __future__ import annotations

from file_reader.platform_browser.ytdlp_platforms import (
    validate_ytdlp_site_registry,
    ytdlp_allowed,
    ytdlp_platform_id_for_url,
)


def test_ytdlp_platform_id_douyin() -> None:
    """Douyin watch URLs map to douyin."""
    assert ytdlp_platform_id_for_url("https://www.douyin.com/video/7505453424973024549") == "douyin"


def test_ytdlp_platform_id_tiktok() -> None:
    """TikTok watch URLs map to tiktok."""
    assert ytdlp_platform_id_for_url("https://www.tiktok.com/@user/video/123") == "tiktok"


def test_ytdlp_allowed_bilibili() -> None:
    """Bilibili remains supported."""
    assert ytdlp_allowed("https://www.bilibili.com/video/BV1xx411c7mD") is True


def test_ytdlp_site_registry_matches_sites() -> None:
    """Every yt-dlp host suffix is registered in sites.py."""
    validate_ytdlp_site_registry()
