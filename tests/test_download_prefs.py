"""Tests for per-platform download folder preferences."""

from __future__ import annotations


from file_reader.platform_browser.download_prefs import (
    remember_download_dir,
    resolve_download_dir,
    saved_download_dir,
)
from file_reader.platform_browser.sites import get_platform


def test_remember_and_resolve_download_dir(tmp_path, monkeypatch) -> None:
    """Saved folders override the default download path."""
    prefs_file = tmp_path / "platform_download_folders.json"
    monkeypatch.setattr(
        "file_reader.platform_browser.download_prefs._PREFS_PATH",
        prefs_file,
    )
    site = get_platform("bilibili")
    target = tmp_path / "custom-bilibili"
    remember_download_dir(site.site_id, target)
    assert saved_download_dir(site.site_id) == target.resolve()
    assert resolve_download_dir(site) == target.resolve()
