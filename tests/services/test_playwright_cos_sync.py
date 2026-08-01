"""Tests for Playwright Chromium COS sync."""

from __future__ import annotations

from pathlib import Path

from services.infrastructure.sync import playwright_cos_sync, playwright_release


def test_chromium_revision_from_cache_path():
    assert (
        playwright_release.chromium_revision_from_path(
            "/home/user/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome"
        )
        == "1228"
    )


def test_chromium_revision_from_tarball_filename():
    assert playwright_release.chromium_revision_from_path("playwright-chromium-1.61.0-linux-x64-r1228.tar.gz") == "1228"


def test_parse_playwright_tarball_version():
    path = Path("playwright-chromium-1.61.0-linux-x64-r1228.tar.gz")
    assert playwright_release.parse_playwright_tarball_version(path) == "1.61.0"


def test_playwright_cos_update_needed_not_installed(monkeypatch):
    monkeypatch.setattr(
        playwright_cos_sync,
        "read_playwright_cos_meta",
        lambda: {"version": "1.61.0", "browser_revision": "1228"},
    )
    monkeypatch.setattr(
        playwright_cos_sync,
        "detect_installed_playwright_browser_version",
        lambda: None,
    )
    plan = playwright_cos_sync.playwright_cos_update_needed()
    assert plan["update_needed"] is True
    assert plan["reason"] == "not_installed"


def test_playwright_cos_update_needed_up_to_date(monkeypatch):
    monkeypatch.setattr(
        playwright_cos_sync,
        "read_playwright_cos_meta",
        lambda: {"version": "1.61.0", "browser_revision": "1228"},
    )
    monkeypatch.setattr(
        playwright_cos_sync,
        "detect_installed_playwright_browser_version",
        lambda: "1.61.0",
    )
    monkeypatch.setattr(
        playwright_cos_sync,
        "detect_installed_chromium_revision",
        lambda: "1228",
    )
    plan = playwright_cos_sync.playwright_cos_update_needed()
    assert plan["update_needed"] is False
    assert plan["reason"] == "up_to_date"


def test_parse_install_deps_dry_run_missing_list():
    stdout = "Missing system dependencies (3):\n  fonts-wqy-zenhei\n  libasound2t64\n  xvfb\n"
    assert playwright_release.parse_install_deps_dry_run(stdout) == [
        "fonts-wqy-zenhei",
        "libasound2t64",
        "xvfb",
    ]


def test_playwright_cos_update_needed_revision_mismatch(monkeypatch):
    monkeypatch.setattr(
        playwright_cos_sync,
        "read_playwright_cos_meta",
        lambda: {"version": "1.61.0", "browser_revision": "1228"},
    )
    monkeypatch.setattr(
        playwright_cos_sync,
        "detect_installed_playwright_browser_version",
        lambda: "1.61.0",
    )
    monkeypatch.setattr(
        playwright_cos_sync,
        "detect_installed_chromium_revision",
        lambda: "1200",
    )
    plan = playwright_cos_sync.playwright_cos_update_needed()
    assert plan["update_needed"] is True
    assert plan["reason"] == "revision_mismatch"
