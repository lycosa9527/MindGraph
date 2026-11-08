"""Public search-engine hints: robots.txt, sitemap, and HTML stamps.

The homepage, the sign-in page, and the static privacy policy are indexable.
Logged-in app routes stay disallowed. The sitemap host follows the public
origin so each deployment advertises itself.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os
import re
from html import escape
from xml.sax.saxutils import escape as xml_escape

# Snippet for Google, Bing, and Baidu. Kept in sync with frontend/index.html.
SEARCH_DESCRIPTION = (
    "MindGraph is the Mind Platform (迈特教研): an AI diagram, mind map, and teaching workspace. "
    "MindGraph（迈特教研）是面向教学的 AI 图示与思维导图平台。"
)

# Paths a signed-out visitor can read. ``/`` is the public homepage.
PUBLIC_INDEX_PATHS = ("/", "/auth", "/privacy")

# Google Search Console HTML-tag content. Public by design; never a secret.
_GOOGLE_SITE_VERIFICATION_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
_HEAD_CLOSE_RE = re.compile(r"</head>", re.IGNORECASE)
_BODY_CLOSE_RE = re.compile(r"</body>", re.IGNORECASE)
_LEGACY_TITLE_RE = re.compile(r"<title>\s*Mind Platform\s*</title>", re.IGNORECASE)
_BRAND_TITLE = "MindGraph · Mind Platform"
_NOSCRIPT_BRAND = (
    "<noscript><p>"
    "MindGraph is the Mind Platform (迈特教研): an AI diagram, mind map, and teaching workspace."
    "</p></noscript>\n  "
)


def build_robots_txt(origin: str) -> str:
    """Return robots.txt that allows the public pages and points at the sitemap."""
    base = origin.rstrip("/")
    lines = [
        "# Exact public URLs only. The signed-in app stays disallowed.",
        "# A trailing $ is the end of the path (Google and Bing).",
        "User-agent: *",
        "Allow: /$",
        "Allow: /auth$",
        "Allow: /privacy$",
        "Allow: /sitemap.xml$",
        "Disallow: /privacy/",
        "Disallow: /privacy-policy.html",
        "Disallow: /",
        "",
        f"Sitemap: {base}/sitemap.xml",
        "",
    ]
    return "\n".join(lines)


def is_indexable_shell_path(url_path: str) -> bool:
    """True only for the homepage and the sign-in page, not nearby paths."""
    return url_path in {"/", "/auth"}


def canonical_href(origin: str, url_path: str) -> str:
    """Absolute canonical URL for an indexable shell path on *origin*."""
    base = origin.rstrip("/")
    if url_path == "/":
        return f"{base}/"
    return f"{base}{url_path.rstrip('/')}"


def build_sitemap_xml(origin: str) -> str:
    """Return a urlset for the public pages on *origin*."""
    base = origin.rstrip("/")
    urls = "\n".join(f"  <url><loc>{xml_escape(base + path)}</loc></url>" for path in PUBLIC_INDEX_PATHS)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )


def _robots_rule_specificity(url_path: str, rule: str) -> int:
    """Return how specific *rule* is for *url_path*, or -1 when it does not match.

    A trailing ``$`` anchors the rule to the end of the path. The length includes
    that anchor, so ``Allow: /$`` (the homepage) beats ``Disallow: /``.
    """
    if rule.endswith("$"):
        if url_path != rule[:-1]:
            return -1
        return len(rule)
    if url_path.startswith(rule):
        return len(rule)
    return -1


def robots_allows(robots_txt: str, url_path: str) -> bool:
    """Google longest-match: the longest rule wins; equal length prefers Allow."""
    best_len = -1
    best_allow: bool | None = None
    for raw_line in robots_txt.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        directive = key.strip().lower()
        rule = value.strip()
        if directive not in {"allow", "disallow"} or not rule:
            continue
        rule_len = _robots_rule_specificity(url_path, rule)
        if rule_len < 0:
            continue
        if rule_len > best_len:
            best_len = rule_len
            best_allow = directive == "allow"
        elif rule_len == best_len and directive == "allow":
            best_allow = True
    if best_allow is None:
        return True
    return best_allow


def stamp_brand_metadata(html: str) -> str:
    """Put the product names in the shell even when dist was built before this change."""
    html = _LEGACY_TITLE_RE.sub(f"<title>{_BRAND_TITLE}</title>", html, count=1)
    if 'name="description"' not in html:
        snippet = f'<meta name="description" content="{escape(SEARCH_DESCRIPTION)}" />\n  '
        html = _insert_before_head_close(html, snippet)
    if "<noscript" not in html.lower():
        match = _BODY_CLOSE_RE.search(html)
        if match is not None:
            html = html[: match.start()] + _NOSCRIPT_BRAND + html[match.start() :]
    return html


def google_site_verification_token(raw: str | None = None) -> str:
    """Return a Search Console HTML-tag token, or empty when unset or invalid."""
    if raw is None:
        raw = os.environ.get("GOOGLE_SITE_VERIFICATION", "")
    token = raw.strip()
    if _GOOGLE_SITE_VERIFICATION_RE.fullmatch(token):
        return token
    return ""


def stamp_google_site_verification(html: str, token: str) -> str:
    """Insert the Search Console verification meta tag when *token* is set."""
    if not token or 'name="google-site-verification"' in html:
        return html
    snippet = f'<meta name="google-site-verification" content="{escape(token, quote=True)}" />\n  '
    return _insert_before_head_close(html, snippet)


def stamp_indexable_document(html: str, canonical: str, verification_token: str = "") -> str:
    """Add the canonical URL and, when set, the Search Console verification tag."""
    html = stamp_canonical_link(html, canonical)
    return stamp_google_site_verification(html, verification_token)


def stamp_canonical_link(html: str, href: str) -> str:
    """Insert a canonical link when the document has a head and none yet."""
    if 'rel="canonical"' in html:
        return html
    snippet = f'<link rel="canonical" href="{escape(href, quote=True)}" />\n  '
    return _insert_before_head_close(html, snippet)


def stamp_noindex(html: str) -> str:
    """Ask crawlers not to index this HTML document."""
    if 'name="robots"' in html:
        return html
    snippet = '<meta name="robots" content="noindex, nofollow" />\n  '
    return _insert_before_head_close(html, snippet)


def _insert_before_head_close(html: str, snippet: str) -> str:
    match = _HEAD_CLOSE_RE.search(html)
    if match is None:
        return html
    return html[: match.start()] + snippet + html[match.start() :]
