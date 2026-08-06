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
    monkeypatch.setattr(playwright_cos_sync, "playwright_package_version", lambda: "1.61.0")
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
    monkeypatch.setattr(playwright_cos_sync, "playwright_package_version", lambda: "1.61.0")
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
    monkeypatch.setattr(playwright_cos_sync, "playwright_package_version", lambda: "1.61.0")
    plan = playwright_cos_sync.playwright_cos_update_needed()
    assert plan["update_needed"] is True
    assert plan["reason"] == "revision_mismatch"


def test_playwright_package_cos_mismatch_package_newer():
    mismatch = playwright_cos_sync.playwright_package_cos_mismatch("1.62.0", "1.60.0")
    assert mismatch is not None
    assert mismatch["reason"] == "package_newer_than_cos"
    assert "1.62.0" in mismatch["hint"]
    assert "1.60.0" in mismatch["hint"]


def test_playwright_package_cos_mismatch_cos_newer():
    mismatch = playwright_cos_sync.playwright_package_cos_mismatch("1.60.0", "1.62.0")
    assert mismatch is not None
    assert mismatch["reason"] == "cos_newer_than_package"
    assert "newer than local" in mismatch["hint"]


def test_playwright_cos_update_needed_package_newer_than_cos(monkeypatch):
    monkeypatch.setattr(
        playwright_cos_sync,
        "read_playwright_cos_meta",
        lambda: {"version": "1.60.0", "browser_revision": "1223"},
    )
    monkeypatch.setattr(
        playwright_cos_sync,
        "detect_installed_playwright_browser_version",
        lambda: None,
    )
    monkeypatch.setattr(playwright_cos_sync, "playwright_package_version", lambda: "1.62.0")
    plan = playwright_cos_sync.playwright_cos_update_needed()
    assert plan["update_needed"] is False
    assert plan["reason"] == "package_newer_than_cos"
    assert plan["package_version"] == "1.62.0"
    assert plan["cos_version"] == "1.60.0"


def test_playwright_cos_update_needed_cos_newer_than_package(monkeypatch):
    monkeypatch.setattr(
        playwright_cos_sync,
        "read_playwright_cos_meta",
        lambda: {"version": "1.62.0", "browser_revision": "1234"},
    )
    monkeypatch.setattr(
        playwright_cos_sync,
        "detect_installed_playwright_browser_version",
        lambda: None,
    )
    monkeypatch.setattr(playwright_cos_sync, "playwright_package_version", lambda: "1.60.0")
    plan = playwright_cos_sync.playwright_cos_update_needed()
    assert plan["update_needed"] is False
    assert plan["reason"] == "cos_newer_than_package"
