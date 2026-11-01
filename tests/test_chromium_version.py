"""Chromium version probes must not launch a browser when --version works."""

from types import SimpleNamespace

import pytest
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


@pytest.mark.asyncio
async def test_startup_diagnostics_checks_cli_version_without_launch(monkeypatch):
    """Startup must not open a Playwright browser pipe."""

    class FakeChromium:
        """Chromium handle whose launch would mean the probe regressed."""

        executable_path = "/opt/ms-playwright/chromium-1234/chrome-linux64/chrome"

        async def launch(self, **_kwargs):
            """Reject a startup browser launch."""
            raise AssertionError("startup diagnostics must not launch Chromium")

    class FakePlaywright:
        """Started Playwright driver with no browser."""

        chromium = FakeChromium()

        async def stop(self):
            """Stop the fake driver."""

    class FakeStarter:
        """Stand-in for ``async_playwright()``."""

        async def start(self):
            """Return the fake driver."""
            return FakePlaywright()

    def chrome_exists(path: str) -> bool:
        return str(path).endswith("chrome")

    def cli_version(_path: str) -> str:
        return "151.0.7922.34"

    monkeypatch.setattr(browser_mod, "async_playwright", FakeStarter)
    monkeypatch.setattr(browser_mod.os.path, "exists", chrome_exists)
    monkeypatch.setattr(browser_mod, "_chromium_cli_version", cli_version)
    await browser_mod.log_browser_diagnostics()
