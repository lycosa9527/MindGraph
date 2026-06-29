"""Tests for yt-dlp extractor helpers."""

from __future__ import annotations

from file_reader.platform_browser.cookie_jar import write_netscape_cookie_file
from file_reader.platform_browser.models import ProbeContext
from file_reader.platform_browser.ytdlp_extractor import (
    platform_id_for_url,
    resolve_page_url,
    ytdlp_probe_status_hint,
)


class _FakeCookie:
    def __init__(self, name: str, value: str, domain: str, path: str = "/") -> None:
        self.name = name
        self.value = value
        self.domain = domain
        self.path = path


def test_platform_id_for_bilibili() -> None:
    """Bilibili URLs map to bilibili platform id."""
    assert platform_id_for_url("https://www.bilibili.com/video/BV1xx411c7mD") == "bilibili"


def test_platform_id_for_youtube() -> None:
    """YouTube URLs map to youtube platform id."""
    assert platform_id_for_url("https://www.youtube.com/watch?v=abc") == "youtube"


def test_write_netscape_cookie_file_filters_domain() -> None:
    """Cookie export writes Netscape format lines."""
    cookies = [_FakeCookie("SESSDATA", "abc", ".bilibili.com")]
    path = write_netscape_cookie_file(cookies, domain_filter="bilibili.com")
    try:
        text = path.read_text(encoding="utf-8")
    finally:
        path.unlink(missing_ok=True)
    assert "SESSDATA" in text
    assert ".bilibili.com" in text
    assert "\t/\t" not in text or "\t/\tTRUE\t" in text or "\tTRUE\t/" in text


def test_write_netscape_cookie_file_uses_cookie_path() -> None:
    """Per-cookie paths are preserved in Netscape export."""
    cookie = _FakeCookie("SESSDATA", "abc", ".bilibili.com", path="/video")
    path = write_netscape_cookie_file([cookie], domain_filter="bilibili.com")
    try:
        text = path.read_text(encoding="utf-8")
    finally:
        path.unlink(missing_ok=True)
    assert "/video" in text


def test_resolve_page_url_non_short_link() -> None:
    """Non-short URLs pass through unchanged."""
    url = "https://www.bilibili.com/video/BV1xx411c7mD"
    assert resolve_page_url(url) == url


def test_write_netscape_cookie_file_export_all() -> None:
    """export_all writes cookies from any domain."""
    cookies = [
        _FakeCookie("sessionid", "abc", ".douyin.com"),
        _FakeCookie("other", "xyz", ".example.com"),
    ]
    path = write_netscape_cookie_file(cookies, domain_filter="douyin.com", export_all=True)
    try:
        text = path.read_text(encoding="utf-8")
    finally:
        path.unlink(missing_ok=True)
    assert "sessionid" in text
    assert "other" in text


def test_ytdlp_probe_status_hint_bilibili() -> None:
    """Bilibili probe failures suggest refreshing cookies."""
    context = ProbeContext(
        page_url="https://www.bilibili.com/video/BV1xx411c7mD",
        login_state={},
        cookies=[],
        smartedu_token="",
    )
    assert ytdlp_probe_status_hint(context, ()) == "ytdlp_cookies_needed"
