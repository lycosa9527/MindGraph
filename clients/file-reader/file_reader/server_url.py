"""Validate and normalize MindGraph server URLs for the file-reader client."""

from __future__ import annotations

from urllib.parse import urlparse

LOCAL_DEV_HOSTS = frozenset({"localhost", "127.0.0.1"})


class ServerUrlError(ValueError):
    """Raised when a server URL is not on the HTTPS allowlist."""


def _host_is_allowed(host: str) -> bool:
    lowered = host.lower()
    if lowered in LOCAL_DEV_HOSTS:
        return True
    return lowered == "mindspringedu.com" or lowered.endswith(".mindspringedu.com")


def normalize_server_url(raw: str) -> str:
    """Return a canonical HTTPS (or local dev HTTP) server base URL."""
    text = (raw or "").strip()
    if not text:
        raise ServerUrlError("Server URL is required")

    parsed = urlparse(text if "://" in text else f"https://{text}")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ServerUrlError("Server URL must include a host name")

    if host in LOCAL_DEV_HOSTS:
        if parsed.scheme not in ("http", "https"):
            raise ServerUrlError("Local dev URLs must use http or https")
    elif parsed.scheme != "https":
        raise ServerUrlError("Only https:// is allowed for MindGraph servers")

    if not _host_is_allowed(host):
        raise ServerUrlError("Server host is not allowed")

    port = parsed.port
    if port is not None and not (host in LOCAL_DEV_HOSTS and parsed.scheme == "http"):
        if port != 443:
            raise ServerUrlError("Only port 443 is allowed for production servers")

    netloc = host
    if port is not None and port not in (80, 443):
        netloc = f"{host}:{port}"
    elif port == 443 and parsed.scheme == "https":
        netloc = host

    return f"{parsed.scheme}://{netloc}"
