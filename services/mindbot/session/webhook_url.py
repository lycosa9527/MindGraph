"""Validate ``sessionWebhook`` URLs from DingTalk callbacks to reduce SSRF risk.

DNS rebinding protection
------------------------
The validation resolves the webhook hostname **once** and returns the pinned IP.
Callers must connect to this pre-resolved IP (not the hostname) so a DNS rebinding
attack cannot redirect subsequent requests to a private address after validation.

Return value: ``(ok: bool, reason: str, pinned_ip: str)``
- ``ok=True`` with ``pinned_ip`` set when the hostname resolved to a public IP.
- ``ok=True`` with ``pinned_ip=""`` when the host was already a literal public IP.
- ``ok=False`` on any rejection; ``pinned_ip`` is always ``""`` in that case.

Callers should pass ``pinned_ip`` to :func:`post_session_webhook` so it uses an
``aiohttp`` resolver that returns the pinned address without re-resolving DNS.
"""

from __future__ import annotations

import asyncio
import functools
import ipaddress
import logging
import os
import socket
from typing import Optional
from urllib.parse import urlparse

from utils.env_helpers import env_bool, env_float

logger = logging.getLogger(__name__)

_DEFAULT_DNS_TIMEOUT = 5.0


@functools.cache
def _dns_timeout() -> float:
    return max(0.5, env_float("MINDBOT_SESSION_WEBHOOK_DNS_TIMEOUT", _DEFAULT_DNS_TIMEOUT))


def _parse_allow_hosts() -> Optional[set[str]]:
    raw = os.getenv("MINDBOT_SESSION_WEBHOOK_ALLOW_HOSTS", "").strip()
    if not raw:
        return None
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def _ip_addr_forbidden(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if addr.is_loopback:
        return True
    if addr.is_link_local:
        return True
    if addr.is_private:
        return True
    if addr.is_reserved:
        return True
    if addr.is_multicast:
        return True
    if addr.version == 4:
        octets = str(addr).split(".")
        if len(octets) == 4 and octets[0] == "0":
            return True
    return False


def _literal_ip_allowed(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> tuple[bool, str]:
    if _ip_addr_forbidden(addr):
        return False, "host is a disallowed address"
    return True, ""


def _getaddrinfo_timeout(host: str, port: int, timeout_sec: float) -> list[tuple]:
    def _resolve() -> list[tuple]:
        return socket.getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )

    return asyncio.wait_for(asyncio.to_thread(_resolve), timeout=timeout_sec)


async def validate_session_webhook_url(url: str) -> tuple[bool, str, str]:
    """
    Return ``(ok, reason, pinned_ip)`` after validating the session webhook URL.

    ``pinned_ip`` is the first resolved IP when ok=True and the host was a
    hostname (not a literal IP).  Pass it to :func:`post_session_webhook` so the
    actual HTTP request connects to this pre-resolved address, preventing DNS
    rebinding attacks.

    Enforces HTTPS by default (optional ``MINDBOT_SESSION_WEBHOOK_ALLOW_HTTP``),
    rejects credentials in the URL, optional host allowlist
    (``MINDBOT_SESSION_WEBHOOK_ALLOW_HOSTS``), and blocks resolved IPs that are
    loopback, private, link-local, reserved, or multicast.
    """
    raw = (url or "").strip()
    if not raw:
        return False, "empty url", ""

    parsed = urlparse(raw)
    if parsed.username or parsed.password:
        return False, "userinfo in url is not allowed", ""

    scheme = (parsed.scheme or "").lower()
    allow_http = env_bool("MINDBOT_SESSION_WEBHOOK_ALLOW_HTTP", False)
    if scheme == "https":
        pass
    elif scheme == "http" and allow_http:
        pass
    else:
        return (False, "only https is allowed" if not allow_http else "invalid scheme", "")

    host = (parsed.hostname or "").strip()
    if not host:
        return False, "missing host", ""

    host_lower = host.lower()
    allow_hosts = _parse_allow_hosts()
    if allow_hosts is not None and host_lower not in allow_hosts:
        return False, "host not in allowlist", ""

    port = parsed.port
    if port is None:
        port = 443 if scheme == "https" else 80

    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        ok, reason = _literal_ip_allowed(addr)
        if not ok:
            return False, reason or "disallowed ip", ""
        # Literal IP: no pinning needed — connect directly to this address.
        return True, "", ""

    try:
        infos = await _getaddrinfo_timeout(host, port, _dns_timeout())
    except asyncio.TimeoutError:
        logger.warning("[MindBot] sessionWebhook DNS timeout for host=%s", host)
        return False, "dns resolution timed out", ""
    except socket.gaierror as exc:
        logger.warning("[MindBot] sessionWebhook DNS failed for host=%s: %s", host, exc)
        return False, "dns resolution failed", ""

    if not infos:
        return False, "dns returned no addresses", ""
    pinned_ip = ""
    for info in infos:
        sockaddr = info[4]
        ip_s = sockaddr[0]
        try:
            addr = ipaddress.ip_address(ip_s)
        except ValueError:
            return False, "invalid resolved address", ""
        if _ip_addr_forbidden(addr):
            return False, "host resolves to a disallowed address", ""
        if not pinned_ip:
            pinned_ip = ip_s
    return True, "", pinned_ip
