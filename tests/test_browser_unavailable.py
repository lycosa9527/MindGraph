"""Unit tests for Playwright browser unavailable mapping."""

from services.infrastructure.utils.browser import (
    BrowserUnavailableError,
    is_browser_unavailable_message,
    wrap_browser_launch_error,
)


def test_is_browser_unavailable_message_detects_missing_executable():
    """Detect classic Playwright missing-binary message."""
    msg = (
        "BrowserType.launch: Executable doesn't exist at "
        "/root/.cache/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell"
    )
    assert is_browser_unavailable_message(msg) is True


def test_wrap_browser_launch_error_maps_playwright_style_message():
    """Map missing-executable RuntimeError to BrowserUnavailableError."""
    exc = RuntimeError("BrowserType.launch: Executable doesn't exist at /tmp/ms-playwright/x")
    wrapped = wrap_browser_launch_error(exc)
    assert isinstance(wrapped, BrowserUnavailableError)


def test_wrap_browser_launch_error_passes_through_other_errors():
    """Non-browser errors stay unchanged."""
    exc = ValueError("unrelated")
    assert wrap_browser_launch_error(exc) is exc
