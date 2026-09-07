"""Chromium version probes must not launch a browser when --version works."""

from types import SimpleNamespace

from playwright.async_api import Playwright

from services.infrastructure.utils import browser as browser_mod
from services.infrastructure.utils.browser import (
    _chromium_executable_for_launch,
    _get_chromium_version,
    _select_best_chromium_executable,
)
from tests.typing_helpers import as_type


def test_get_chromium_version_uses_cli_without_launch(monkeypatch):
    """``--version`` is enough; Playwright launch is not used."""

    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="Chromium 151.0.7922.34\n")

    def boom(*_args, **_kwargs):
        raise AssertionError("sync_playwright should not launch for version detection")

    monkeypatch.setattr(browser_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(browser_mod, "sync_playwright", boom)
    assert _get_chromium_version("/opt/chrome") == "151.0.7922.34"


def test_get_chromium_version_uses_path_revision_when_cli_fails(monkeypatch):
    """Playwright cache path revision is next; still no browser launch."""

    def fake_run(*_args, **_kwargs):
        raise browser_mod.subprocess.TimeoutExpired(cmd="chrome", timeout=3)

    def boom(*_args, **_kwargs):
        raise AssertionError("sync_playwright should not launch when path revision exists")

    monkeypatch.setattr(browser_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(browser_mod, "sync_playwright", boom)
    path = "/root/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome"
    assert _get_chromium_version(path) == "1234"


def test_select_best_chromium_prefers_newer_cli_version(monkeypatch):
    """Local vs Playwright pick uses CLI versions, not a Chromium launch."""

    versions = {
        "/local/chrome": "148.0.7778.96",
        "/pw/chrome": "151.0.7922.34",
    }

    def fake_run(cmd, **_kwargs):
        executable = cmd[0]
        return SimpleNamespace(returncode=0, stdout=f"Chromium {versions[executable]}\n")

    def boom(*_args, **_kwargs):
        raise AssertionError("sync_playwright should not launch to compare versions")

    monkeypatch.setattr(browser_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(browser_mod, "sync_playwright", boom)
    chosen = _select_best_chromium_executable("/local/chrome", "/pw/chrome")
    assert chosen == "/pw/chrome"


def test_launch_executable_uses_playwright_path_without_version_compare(tmp_path, monkeypatch):
    """PNG launch uses the already-started Playwright binary, not a version race."""
    chrome = tmp_path / "chrome"
    chrome.write_bytes(b"")
    playwright_instance = as_type(
        SimpleNamespace(chromium=SimpleNamespace(executable_path=str(chrome))),
        Playwright,
    )

    def boom_local():
        raise AssertionError("local Chromium should not be probed when Playwright path exists")

    monkeypatch.setattr(browser_mod, "_get_local_chromium_executable", boom_local)
    assert _chromium_executable_for_launch(playwright_instance) == str(chrome)
