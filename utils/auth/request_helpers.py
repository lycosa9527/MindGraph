"""
Request Helpers for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Utilities for handling HTTP requests: IP detection, HTTPS check, etc.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os

from fastapi import Request

logger = logging.getLogger(__name__)


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
    if hasattr(request.url, 'scheme') and request.url.scheme == "https":
        return True

    # Check environment variable for production mode (force secure cookies)
    if os.getenv("FORCE_SECURE_COOKIES", "").lower() == "true":
        return True

    return False


def get_client_ip(request: Request) -> str:
    """
    Get real client IP address, even behind reverse proxy (nginx, etc.)

    Checks headers in order:
    1. X-Forwarded-For (most common, can be comma-separated)
    2. X-Real-IP (nginx specific)
    3. request.client.host (fallback, direct connection)

    Args:
        request: FastAPI Request object

    Returns:
        Client IP address string

    Example:
        With nginx proxy_pass:
        X-Forwarded-For: 203.0.113.45, 198.51.100.178
        Returns: 203.0.113.45 (leftmost = original client)
    """
    # Check X-Forwarded-For header (most common with reverse proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs: "client, proxy1, proxy2"
        # The leftmost is the original client IP
        client_ip = forwarded_for.split(",")[0].strip()
        logger.debug(
            "Client IP from X-Forwarded-For: %s (full: %s)", client_ip, forwarded_for
        )
        return client_ip

    # Check X-Real-IP header (nginx-specific)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        logger.debug("Client IP from X-Real-IP: %s", real_ip)
        return real_ip

    # Fallback to direct connection IP
    direct_ip = request.client.host if request.client else "unknown"
    logger.debug("Client IP from request.client.host: %s", direct_ip)
    return direct_ip
