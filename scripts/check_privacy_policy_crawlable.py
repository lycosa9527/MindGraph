"""Validate static privacy policy HTML is crawler-readable (Chrome Web Store)."""

from __future__ import annotations

import re
import sys

from utils.privacy_policy_static import (
    _EXTENSION_SECTION_ID,
    build_privacy_policy_html,
    privacy_policy_source_path,
)

_SCRIPT_TAG_RE = re.compile(r"<script\b", re.IGNORECASE)
_MODULE_SCRIPT_RE = re.compile(r"""<script[^>]*\btype\s*=\s*["']module["']""", re.IGNORECASE)
_REQUIRED_PHRASES = (
    "MindGraph Terms of Use",
    "Information we collect",
    "browser extension",
    "chrome.storage.local",
    "mgat_",
)


def is_google_crawlable_privacy_html(html: str) -> tuple[bool, list[str]]:
    """Return whether HTML is suitable for store crawlers and any failure reasons."""
    issues: list[str] = []
    if "<!DOCTYPE html>" not in html:
        issues.append("missing <!DOCTYPE html>")
    if _SCRIPT_TAG_RE.search(html):
        issues.append("contains <script> (crawlers may not execute JS)")
    if _MODULE_SCRIPT_RE.search(html):
        issues.append("contains ES module script")
    if f'id="{_EXTENSION_SECTION_ID}"' not in html:
        issues.append(f'missing id="{_EXTENSION_SECTION_ID}" appendix anchor')
    lowered = html.lower()
    for phrase in _REQUIRED_PHRASES:
        if phrase.lower() not in lowered:
            issues.append(f'missing required phrase: "{phrase}"')
    if len(html) < 1500:
        issues.append("body too short for a privacy policy")
    return (len(issues) == 0, issues)


def main() -> int:
    """Check generated privacy-policy.html on disk."""
    source = privacy_policy_source_path()
    if not source.is_file():
        print(f"ERROR: privacy policy file missing: {source}", file=sys.stderr)
        print("Run: PYTHONPATH=. python scripts/render_privacy_policy_html.py", file=sys.stderr)
        return 1

    html = source.read_text(encoding="utf-8")
    ok, issues = is_google_crawlable_privacy_html(html)
    if not ok:
        for issue in issues:
            print(f"ERROR: {issue}", file=sys.stderr)
        return 1

    built = build_privacy_policy_html()
    built_ok, built_issues = is_google_crawlable_privacy_html(built)
    if not built_ok:
        for issue in built_issues:
            print(f"ERROR: generator output invalid: {issue}", file=sys.stderr)
        return 1

    print(f"OK: {source} is Google-crawlable ({len(html)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
