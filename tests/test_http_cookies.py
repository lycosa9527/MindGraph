"""Tests for HTTP cookie filtering helpers."""

from __future__ import annotations

import time

from file_reader.platform_browser.http_cookies import (
    build_cookie_header,
    cookie_applies_to_url,
    cookie_expired,
    filter_cookies_for_url,
)


class _FakeCookie:
    def __init__(
        self,
        name: str,
        value: str,
        domain: str,
        *,
        expires: float | None = None,
    ) -> None:
        self.name = name
        self.value = value
        self.domain = domain
        self.expires = expires


def test_cookie_applies_to_subdomain() -> None:
    """Cookie domains match request hosts."""
    cookie = _FakeCookie("sessionid", "abc", ".qq.com")
    assert cookie_applies_to_url(cookie, "https://finder.video.qq.com/stodownload") is True


def test_filter_cookies_for_url_skips_expired() -> None:
    """Expired cookies are excluded from scoped headers."""
    cookies = [
        _FakeCookie("live", "yes", ".qq.com"),
        _FakeCookie("dead", "no", ".qq.com", expires=time.time() - 60),
    ]
    filtered = filter_cookies_for_url(cookies, "https://finder.video.qq.com/stodownload")
    assert len(filtered) == 1
    assert filtered[0].name == "live"


def test_build_cookie_header_scopes_to_url() -> None:
    """Only matching cookies are serialized."""
    cookies = [
        _FakeCookie("a", "1", ".bilibili.com"),
        _FakeCookie("b", "2", ".example.com"),
    ]
    header = build_cookie_header(cookies, "https://www.bilibili.com/video/BV1")
    assert header == "a=1"


def test_cookie_expired_false_for_session_cookie() -> None:
    """Session cookies without expiry are kept."""
    cookie = _FakeCookie("sess", "abc", ".example.com", expires=0)
    assert cookie_expired(cookie) is False
