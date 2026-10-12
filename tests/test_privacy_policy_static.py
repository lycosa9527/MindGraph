"""Tests for static privacy policy HTML (Chrome Web Store crawlability)."""

from __future__ import annotations

import re

from scripts.check_privacy_policy_crawlable import is_google_crawlable_privacy_html
from utils.privacy_policy_static import (
    _EXTENSION_SECTION_ID,
    _PRIVACY_POLICY_SECTION_ID,
    _USER_AGREEMENT_SECTION_ID,
    build_privacy_policy_html,
    write_privacy_policy_files,
)


def test_build_privacy_policy_html_has_extension_appendix() -> None:
    """Static HTML includes extension appendix for store crawlers."""
    html = build_privacy_policy_html()
    assert "<!DOCTYPE html>" in html
    assert f'id="{_EXTENSION_SECTION_ID}"' in html
    assert "browser extension" in html.lower()
    assert "mgat_" in html
    assert "chrome.storage.local" in html
    assert "Limited Use" in html
    ok, issues = is_google_crawlable_privacy_html(html)
    assert ok, issues


def test_privacy_policy_sections_are_numbered_from_one() -> None:
    """Public /privacy headings match the in-app agreement: 1 through 18, no gaps."""
    html = build_privacy_policy_html()
    titles = re.findall(r"<h2>(.*?)</h2>", html)
    numbers = [int(title.split(".", 1)[0]) for title in titles if title[:1].isdigit()]
    assert numbers == list(range(1, 19))
    assert f'id="{_USER_AGREEMENT_SECTION_ID}"><h2>1. Acceptance and scope</h2>' in html
    assert f'id="{_PRIVACY_POLICY_SECTION_ID}"><h2>5. Information we collect</h2>' in html


def test_write_privacy_policy_files_creates_both_paths(tmp_path, monkeypatch) -> None:
    """Generator writes frontend/public and static copies."""
    public = tmp_path / "frontend" / "public" / "privacy-policy.html"
    static = tmp_path / "static" / "privacy-policy.html"
    monkeypatch.setattr(
        "utils.privacy_policy_static._PRIVACY_HTML_PATHS",
        (public, static),
    )
    written = write_privacy_policy_files()
    assert written == [public, static]
    assert public.is_file()
    assert static.is_file()
    assert "MindGraph Terms of Use" in public.read_text(encoding="utf-8")
