"""Tests for SmartEdu embedded browser helpers."""

from __future__ import annotations

import os

from file_reader.smartedu_browser import (
    DEFAULT_HOME_URL,
    configure_webview_storage,
    merge_cookie_login_flags,
    normalize_nav_url,
    parse_login_state,
)


class _FakeCookie:
    def __init__(self, name: str, domain: str) -> None:
        self.name = name
        self.domain = domain


def test_normalize_nav_url_defaults() -> None:
    """Empty address bar falls back to smartedu home."""
    assert normalize_nav_url("") == DEFAULT_HOME_URL
    assert normalize_nav_url("  ") == DEFAULT_HOME_URL


def test_normalize_nav_url_adds_https() -> None:
    """Bare hostnames get https prefix."""
    assert normalize_nav_url("www.baidu.com") == "https://www.baidu.com"


def test_parse_login_state_json() -> None:
    """Parse evaluate_js JSON payload."""
    raw = '{"smartedu_logged_in": true, "access_token": "abc"}'
    state = parse_login_state(raw)
    assert state["smartedu_logged_in"] is True
    assert state["access_token"] == "abc"


def test_merge_cookie_login_flags_baidu() -> None:
    """Detect Baidu session from WebView cookie jar."""
    state = merge_cookie_login_flags({}, [_FakeCookie("BDUSS", ".baidu.com")])
    assert state["baidu_logged_in"] is True


def test_merge_cookie_login_flags_bilibili() -> None:
    """Detect Bilibili session from SESSDATA cookie."""
    state = merge_cookie_login_flags({}, [_FakeCookie("SESSDATA", ".bilibili.com")])
    assert state["bilibili_logged_in"] is True


def test_default_home_url_basic_smartedu() -> None:
    """Default home uses basic.smartedu.cn portal."""
    assert DEFAULT_HOME_URL == "https://basic.smartedu.cn/"


def test_configure_webview_storage_sets_env(monkeypatch, tmp_path) -> None:
    """WebView2 user-data folder is configured before widget creation."""
    monkeypatch.delenv("WEBVIEW2_USER_DATA_FOLDER", raising=False)
    folder = configure_webview_storage(tmp_path / "platform-browser" / "webview2")
    assert folder == str((tmp_path / "platform-browser" / "webview2").resolve())
    assert os.environ["WEBVIEW2_USER_DATA_FOLDER"] == folder
