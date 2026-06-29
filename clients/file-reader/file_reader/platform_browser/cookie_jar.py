"""Write browser cookies to a Netscape cookie file for yt-dlp."""

from __future__ import annotations

import atexit
import tempfile
import time
from pathlib import Path
from typing import Any

from file_reader.platform_browser.http_cookies import cookie_expired
from file_reader.settings import SETTINGS_DIR

_COOKIE_TEMP_DIR = SETTINGS_DIR / "platform-browser" / "cookie-temp"
_STALE_COOKIE_GLOB = "mindgraph-cookies-*.txt"


class _CookieCleanupState:
    registered = False


def _register_cookie_cleanup() -> None:
    if _CookieCleanupState.registered:
        return
    atexit.register(cleanup_stale_cookie_files)
    _CookieCleanupState.registered = True


def cleanup_stale_cookie_files() -> None:
    """Remove leftover temp cookie files from prior runs."""
    if not _COOKIE_TEMP_DIR.is_dir():
        return
    for path in _COOKIE_TEMP_DIR.glob(_STALE_COOKIE_GLOB):
        try:
            path.unlink()
        except OSError:
            continue


def write_netscape_cookie_file(
    cookies: list[Any],
    *,
    domain_filter: str = "",
    export_all: bool = False,
) -> Path:
    """Serialize WebView cookies to a temp Netscape cookie file."""
    _register_cookie_cleanup()
    _COOKIE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    current = time.time()
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".txt",
        delete=False,
        prefix="mindgraph-cookies-",
        dir=_COOKIE_TEMP_DIR,
    ) as handle:
        path = Path(handle.name)
        handle.write("# Netscape HTTP Cookie File\n")
        domain_suffix = domain_filter.lower().lstrip(".")
        for cookie in cookies:
            name = str(getattr(cookie, "name", "") or "")
            value = str(getattr(cookie, "value", "") or "")
            domain = str(getattr(cookie, "domain", "") or "")
            if not name or not domain:
                continue
            if cookie_expired(cookie, now=current):
                continue
            if not export_all and domain_suffix:
                cookie_domain = domain.lower().lstrip(".")
                if domain_suffix not in cookie_domain and not cookie_domain.endswith(domain_suffix):
                    root_suffix = ".".join(domain_suffix.split(".")[-2:])
                    if root_suffix and root_suffix not in cookie_domain:
                        continue
            path_attr = "TRUE" if domain.startswith(".") else "FALSE"
            cookie_domain = domain if domain.startswith(".") else f".{domain}"
            secure = "TRUE" if bool(getattr(cookie, "secure", False)) else "FALSE"
            expires = getattr(cookie, "expires", None)
            expiry = "0"
            if isinstance(expires, (int, float)) and expires > 0:
                expiry = str(int(expires))
            cookie_path = str(getattr(cookie, "path", "") or "/")
            if not cookie_path.startswith("/"):
                cookie_path = f"/{cookie_path}"
            handle.write(
                f"{cookie_domain}\t{path_attr}\t{cookie_path}\t{secure}\t{expiry}\t{name}\t{value}\n",
            )
    return path
