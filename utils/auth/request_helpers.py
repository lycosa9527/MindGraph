"""
Request Helpers for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Utilities for handling HTTP requests: IP detection, HTTPS check, etc.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import ipaddress
import logging
import os
import secrets
from functools import lru_cache
from typing import Optional

from fastapi import Request, Response

from utils.auth.config import TRUSTED_PROXY_IPS
from utils.auth.connection_types import HttpOrWebSocket

logger = logging.getLogger(__name__)

# Sentinel keyword expansions for ``TRUSTED_PROXY_IPS``. Using ``private`` lets
# reverse-proxy deployments (Nginx Proxy Manager, Docker, LAN nginx) trust any
# proxy peer without pinning a container IP that changes on recreation.
_PRIVATE_PROXY_NETWORKS = (
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "::1/128",
    "fc00::/7",
)
_LOOPBACK_PROXY_NETWORKS = ("127.0.0.0/8", "::1/128")

# Double-submit CSRF cookie/header names (shared by middleware and auth routers).
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
_CSRF_COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days


def generate_csrf_token() -> str:
    """Return a new cryptographically-random CSRF token."""
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, request: Request, token: Optional[str] = None) -> str:
    """
    Set the double-submit ``csrf_token`` cookie with consistent flags.

    The cookie is intentionally readable by JavaScript (``httponly=False``) so the
    SPA can echo it back in the ``X-CSRF-Token`` header. ``SameSite=strict`` keeps it
    from being sent on cross-site navigations.

    Returns:
        The CSRF token written to the cookie.
    """
    csrf_token = token or generate_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=is_https(request),
        samesite="strict",
        path="/",
        max_age=_CSRF_COOKIE_MAX_AGE,
    )
    return csrf_token


def is_https(request: Request) -> bool:
    """
    Detect if request is over HTTPS

    Checks multiple sources:
    1. X-Forwarded-Proto header (set by reverse proxy like Nginx)
    2. Request URL scheme
    3. FORCE_SECURE_COOKIES environment variable (for production)

    Args:
        request: FastAPI Request object

    Returns:
        True if HTTPS detected, False otherwise
    """
    # Check X-Forwarded-Proto header (set by reverse proxy)
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "").lower()
    if forwarded_proto == "https":
        return True

    # Check if URL scheme is https
    if hasattr(request.url, "scheme") and request.url.scheme == "https":
        return True

    # Check environment variable for production mode (force secure cookies)
    if os.getenv("FORCE_SECURE_COOKIES", "").lower() == "true":
        return True

    return False


def _direct_peer_ip(connection: HttpOrWebSocket) -> str:
    return connection.client.host if connection.client else "unknown"


@lru_cache(maxsize=8)
def _parse_trusted_proxy_entries(
    entries: tuple[str, ...],
) -> tuple[tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...], frozenset[str]]:
    """
    Compile ``TRUSTED_PROXY_IPS`` entries into networks + literal fallbacks.

    Supports plain IPs, CIDR ranges, and the ``private`` / ``loopback`` keywords.
    Cached by the (hashable) entries tuple; rebuilt automatically when the config
    list changes (including monkeypatching in tests).
    """
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    literals: set[str] = set()
    for raw in entries:
        token = raw.strip()
        if not token:
            continue
        lowered = token.lower()
        if lowered == "private":
            networks.extend(ipaddress.ip_network(net) for net in _PRIVATE_PROXY_NETWORKS)
            continue
        if lowered == "loopback":
            networks.extend(ipaddress.ip_network(net) for net in _LOOPBACK_PROXY_NETWORKS)
            continue
        try:
            networks.append(ipaddress.ip_network(token, strict=False))
        except ValueError:
            # Non-IP token (e.g. legacy hostname); keep for exact string match.
            literals.add(token)
    return tuple(networks), frozenset(literals)


def _trusted_proxy_peer(connection: HttpOrWebSocket) -> bool:
    if not TRUSTED_PROXY_IPS:
        return False
    direct_ip = _direct_peer_ip(connection)
    networks, literals = _parse_trusted_proxy_entries(tuple(TRUSTED_PROXY_IPS))
    if direct_ip in literals:
        return True
    try:
        peer = ipaddress.ip_address(direct_ip)
    except ValueError:
        return False
    return any(peer in network for network in networks)


def get_client_ip(connection: HttpOrWebSocket) -> str:
    """
    Get real client IP address, even behind reverse proxy (nginx, etc.)

    Forwarded headers (``X-Forwarded-For``, ``X-Real-IP``) are honored only when
    the immediate peer matches ``TRUSTED_PROXY_IPS`` (exact IP, CIDR range, or the
    ``private`` / ``loopback`` keywords). Otherwise the direct connection IP is
    returned to prevent header spoofing.

    Args:
        connection: FastAPI Request or WebSocket

    Returns:
        Client IP address string
    """
    if not _trusted_proxy_peer(connection):
        direct_ip = _direct_peer_ip(connection)
        logger.debug("Client IP from direct connection: %s", direct_ip)
        return direct_ip

    forwarded_for = connection.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
        logger.debug("Client IP from X-Forwarded-For: %s (full: %s)", client_ip, forwarded_for)
        return client_ip

    real_ip = connection.headers.get("X-Real-IP")
    if real_ip:
        logger.debug("Client IP from X-Real-IP: %s", real_ip)
        return real_ip.strip()

    direct_ip = _direct_peer_ip(connection)
    logger.debug("Client IP from connection.client.host: %s", direct_ip)
    return direct_ip


def describe_trusted_proxy_config() -> str:
    """
    Human-readable summary of how ``TRUSTED_PROXY_IPS`` resolved, for startup logs.

    Lets operators confirm at boot whether forwarded-header trust is active (e.g.
    behind Nginx Proxy Manager) or whether the direct peer IP is being used.
    """
    entries = tuple(TRUSTED_PROXY_IPS)
    if not entries:
        return (
            "TRUSTED_PROXY_IPS empty -> forwarded headers IGNORED, using direct peer IP "
            "(set TRUSTED_PROXY_IPS=private when behind a reverse proxy)"
        )
    networks, literals = _parse_trusted_proxy_entries(entries)
    parts: list[str] = [f"{len(networks)} network range(s)"]
    if literals:
        parts.append(f"{len(literals)} literal host(s)")
    return (
        f"TRUSTED_PROXY_IPS={','.join(entries)} -> trusting {', '.join(parts)}; "
        "X-Forwarded-For / X-Real-IP honored from matching peers"
    )
