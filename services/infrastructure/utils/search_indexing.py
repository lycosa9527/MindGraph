"""Public search-engine hints: robots.txt, sitemap, and HTML stamps.

Only the sign-in page and the static privacy policy are indexable. Logged-in
app routes stay disallowed. The sitemap host follows the public origin so each
deployment advertises itself.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from html import escape
from xml.sax.saxutils import escape as xml_escape

# Snippet for Google, Bing, and Baidu. Kept in sync with frontend/index.html.
SEARCH_DESCRIPTION = (
    "MindGraph is the Mind Platform (迈特教研): an AI diagram, mind map, and teaching workspace. "
    "MindGraph（迈特教研）是面向教学的 AI 图示与思维导图平台。"
)

# Paths a signed-out visitor can read. ``/`` is an empty router placeholder.
PUBLIC_INDEX_PATHS = ("/auth", "/privacy")

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
        "# Public sign-in and privacy pages only. The signed-in app stays disallowed.",
        "User-agent: *",
        "Allow: /auth",
        "Allow: /privacy",
        "Allow: /sitemap.xml",
        "Disallow: /privacy/",
        "Disallow: /privacy-policy.html",
        "Disallow: /",
        "",
        f"Sitemap: {base}/sitemap.xml",
        "",
    ]
    return "\n".join(lines)


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
        if not url_path.startswith(rule):
            continue
        rule_len = len(rule)
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
