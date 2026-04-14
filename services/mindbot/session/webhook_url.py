"""Validate ``sessionWebhook`` URLs from DingTalk callbacks to reduce SSRF risk."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
import socket
from typing import Optional
from urllib.parse import urlparse

from utils.env_helpers import env_bool

logger = logging.getLogger(__name__)

_DEFAULT_DNS_TIMEOUT = 5.0


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


async def validate_session_webhook_url(url: str) -> tuple[bool, str]:
    """
    Return (True, "") if ``url`` is allowed, else (False, reason).

    Enforces HTTPS by default (optional ``MINDBOT_SESSION_WEBHOOK_ALLOW_HTTP``),
    rejects credentials in the URL, optional host allowlist
    (``MINDBOT_SESSION_WEBHOOK_ALLOW_HOSTS``), and blocks resolved IPs that are
    loopback, private, link-local, reserved, or multicast.
    """
    raw = (url or "").strip()
    if not raw:
        return False, "empty url"

    parsed = urlparse(raw)
    if parsed.username or parsed.password:
        return False, "userinfo in url is not allowed"

    scheme = (parsed.scheme or "").lower()
    allow_http = env_bool("MINDBOT_SESSION_WEBHOOK_ALLOW_HTTP", False)
    if scheme == "https":
        pass
    elif scheme == "http" and allow_http:
        pass
    else:
        return False, "only https is allowed" if not allow_http else "invalid scheme"

    host = (parsed.hostname or "").strip()
    if not host:
        return False, "missing host"

    host_lower = host.lower()
    allow_hosts = _parse_allow_hosts()
    if allow_hosts is not None and host_lower not in allow_hosts:
        return False, "host not in allowlist"

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
            return False, reason or "disallowed ip"
        return True, ""

    timeout = float(os.getenv("MINDBOT_SESSION_WEBHOOK_DNS_TIMEOUT", str(_DEFAULT_DNS_TIMEOUT)))
    try:
        infos = await _getaddrinfo_timeout(host, port, timeout)
    except asyncio.TimeoutError:
        logger.warning("[MindBot] sessionWebhook DNS timeout for host=%s", host)
        return False, "dns resolution timed out"
    except socket.gaierror as exc:
        logger.warning("[MindBot] sessionWebhook DNS failed for host=%s: %s", host, exc)
        return False, "dns resolution failed"

    for info in infos:
        sockaddr = info[4]
        ip_s = sockaddr[0]
        try:
            addr = ipaddress.ip_address(ip_s)
        except ValueError:
            return False, "invalid resolved address"
        if _ip_addr_forbidden(addr):
            return False, "host resolves to a disallowed address"
    return True, ""
