"""Tests for Playwright browser host helpers."""

from __future__ import annotations

import os
import types

import pytest

from file_reader.platform_browser import playwright_env
from file_reader.platform_browser.playwright_host import (
    PlaywrightPlatformBrowser,
    unwrap_browser_command_result,
)
from file_reader.platform_browser.webview_host import EmbeddedPlatformBrowser


def test_unwrap_browser_command_result_returns_value() -> None:
    """Successful command results pass through unchanged."""
    assert unwrap_browser_command_result("ok") == "ok"


def test_unwrap_browser_command_result_raises() -> None:
    """Worker-thread failures propagate to callers."""
    with pytest.raises(RuntimeError, match="boom"):
        unwrap_browser_command_result(RuntimeError("boom"))


def test_configure_playwright_runtime_sets_node_path(monkeypatch, tmp_path) -> None:
    """Frozen exe layout sets PLAYWRIGHT_NODEJS_PATH to bundled node.exe."""
    driver_dir = tmp_path / "playwright" / "driver"
    driver_dir.mkdir(parents=True)
    node_exe = driver_dir / "node.exe"
    node_exe.write_bytes(b"")
    fake_sys = types.SimpleNamespace(frozen=True, _MEIPASS=str(tmp_path))
    monkeypatch.setattr(playwright_env, "sys", fake_sys)
    monkeypatch.delenv("PLAYWRIGHT_NODEJS_PATH", raising=False)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    result = playwright_env.configure_playwright_runtime()
    assert result == driver_dir
    assert os.environ["PLAYWRIGHT_NODEJS_PATH"] == str(node_exe)
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == "0"


def test_bundled_chromium_executable_detects_chrome_win64(monkeypatch, tmp_path) -> None:
    """Bundled browser lookup finds chrome.exe under .local-browsers."""
    driver_dir = tmp_path / "playwright" / "driver"
    chrome_exe = driver_dir / "package" / ".local-browsers" / "chromium-9999" / "chrome-win64" / "chrome.exe"
    chrome_exe.parent.mkdir(parents=True)
    chrome_exe.write_bytes(b"")
    fake_sys = types.SimpleNamespace(frozen=True, _MEIPASS=str(tmp_path))
    monkeypatch.setattr(playwright_env, "sys", fake_sys)
    assert playwright_env.bundled_chromium_executable() == chrome_exe


def test_playwright_browser_does_not_support_hook_failure() -> None:
    """Playwright backend never surfaces WebView2 hook-failure status."""
    host = PlaywrightPlatformBrowser.__new__(PlaywrightPlatformBrowser)
    assert host.supports_resource_hook_failure is False


def test_embedded_browser_supports_hook_failure() -> None:
    """WebView2 backend can disable capture when Core hooks fail."""
    host = EmbeddedPlatformBrowser.__new__(EmbeddedPlatformBrowser)
    assert host.supports_resource_hook_failure is True
