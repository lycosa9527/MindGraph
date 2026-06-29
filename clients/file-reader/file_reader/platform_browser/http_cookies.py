"""Filter WebView cookies for outbound HTTP requests."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse


def cookie_expired(cookie: Any, *, now: float | None = None) -> bool:
    """Return True when a cookie expiry timestamp is in the past."""
    expires = getattr(cookie, "expires", None)
    if not isinstance(expires, (int, float)) or expires <= 0:
        return False
    current = time.time() if now is None else now
    return expires < current


def cookie_applies_to_url(cookie: Any, request_url: str) -> bool:
    """Return True when a cookie domain matches the request host."""
    host = (urlparse(request_url).hostname or "").lower()
    domain = str(getattr(cookie, "domain", "") or "").lower().lstrip(".")
    if not host or not domain:
        return False
    if host == domain:
        return True
    if host.endswith(f".{domain}"):
        return True
    return domain.startswith(".") and host.endswith(domain.lstrip("."))


def filter_cookies_for_url(cookies: list[Any], request_url: str) -> list[Any]:
    """Return non-expired cookies applicable to a request URL."""
    current = time.time()
    return [
        cookie
        for cookie in cookies
        if not cookie_expired(cookie, now=current) and cookie_applies_to_url(cookie, request_url)
    ]


def build_cookie_header(cookies: list[Any], request_url: str) -> str:
    """Build a Cookie header scoped to the request URL."""
    parts: list[str] = []
    for cookie in filter_cookies_for_url(cookies, request_url):
        name = str(getattr(cookie, "name", "") or "")
        value = str(getattr(cookie, "value", "") or "")
        if name and value:
            parts.append(f"{name}={value}")
    return "; ".join(parts)
