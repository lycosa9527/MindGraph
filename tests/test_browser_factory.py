"""Tests for browser backend selection and cookie normalization."""

from __future__ import annotations

from file_reader.platform_browser.browser_factory import preferred_browser_backend
from file_reader.platform_browser.cookie_jar import write_netscape_cookie_file
from file_reader.platform_browser.cookie_view import CookieView, normalize_cookie
from file_reader.smartedu_browser import browser_storage_path, playwright_storage_path


def test_preferred_browser_backend_defaults_to_playwright(monkeypatch) -> None:
    """Playwright is the default platform browser backend."""
    monkeypatch.delenv("MINDGRAPH_BROWSER", raising=False)
    assert preferred_browser_backend() == "playwright"


def test_preferred_browser_backend_webview2_env(monkeypatch) -> None:
    """MINDGRAPH_BROWSER=webview2 selects the embedded backend."""
    monkeypatch.setenv("MINDGRAPH_BROWSER", "webview2")
    assert preferred_browser_backend() == "webview2"


def test_normalize_cookie_from_mapping() -> None:
    """Playwright cookie dicts map to CookieView with path and secure flags."""
    view = normalize_cookie(
        {
            "name": "SESSDATA",
            "value": "abc",
            "domain": ".bilibili.com",
            "expires": 9999999999,
            "path": "/",
            "secure": True,
        },
    )
    assert isinstance(view, CookieView)
    assert view.name == "SESSDATA"
    assert view.domain == ".bilibili.com"
    assert view.path == "/"
    assert view.secure is True


def test_netscape_cookie_session_expiry(tmp_path, monkeypatch) -> None:
    """Session cookies export as expiry 0, not -1."""
    monkeypatch.setattr(
        "file_reader.platform_browser.cookie_jar.SETTINGS_DIR",
        tmp_path,
    )
    cookies = [
        CookieView(name="sid", value="1", domain=".example.com", expires=-1, path="/", secure=True),
    ]
    path = write_netscape_cookie_file(cookies, export_all=True)
    text = path.read_text(encoding="utf-8")
    assert "\t0\tsid\t1\n" in text
    assert "TRUE\t/" in text


def test_playwright_and_webview_storage_paths_differ(tmp_path, monkeypatch) -> None:
    """Separate profile folders avoid collisions between backends."""
    monkeypatch.setattr("file_reader.smartedu_browser.SETTINGS_DIR", tmp_path)
    assert browser_storage_path() != playwright_storage_path()
    assert browser_storage_path().name == "webview2"
    assert playwright_storage_path().name == "playwright-edge"
