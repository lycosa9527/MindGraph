"""Tests for WebView2 init error typing."""

from __future__ import annotations

from file_reader.platform_browser.webview_host import webview_init_error_types


def test_webview_init_error_types_includes_runtime_errors() -> None:
    """WebView2 creation errors include common Python exception bases."""
    types = webview_init_error_types()
    assert RuntimeError in types
    assert OSError in types
    assert ValueError in types
