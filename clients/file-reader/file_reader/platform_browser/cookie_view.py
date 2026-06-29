"""Normalize cookie records from WebView2 or Playwright."""

from __future__ import annotations

from typing import Any


class CookieView:
    """Attribute-style view over a browser cookie mapping."""

    __slots__ = ("domain", "expires", "name", "path", "secure", "value")

    def __init__(
        self,
        *,
        name: str,
        value: str,
        domain: str,
        expires: float | int = -1,
        path: str = "/",
        secure: bool = False,
    ) -> None:
        self.name = name
        self.value = value
        self.domain = domain
        self.expires = expires
        self.path = path
        self.secure = secure


def normalize_cookie(cookie: Any) -> CookieView:
    """Return a CookieView for dict-like or attribute-like cookie objects."""
    if isinstance(cookie, CookieView):
        return cookie
    if isinstance(cookie, dict):
        expires = cookie.get("expires", -1)
        if not isinstance(expires, (int, float)):
            expires = -1
        return CookieView(
            name=str(cookie.get("name", "") or ""),
            value=str(cookie.get("value", "") or ""),
            domain=str(cookie.get("domain", "") or ""),
            expires=expires,
            path=str(cookie.get("path", "") or "/"),
            secure=bool(cookie.get("secure", False)),
        )
    expires = getattr(cookie, "expires", -1)
    if not isinstance(expires, (int, float)):
        expires = -1
    return CookieView(
        name=str(getattr(cookie, "name", "") or ""),
        value=str(getattr(cookie, "value", "") or ""),
        domain=str(getattr(cookie, "domain", "") or ""),
        expires=expires,
        path=str(getattr(cookie, "path", "") or "/"),
        secure=bool(getattr(cookie, "secure", False)),
    )
