"""
IP Whitelist for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Functions for managing IP whitelist in bayi mode.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import ipaddress
import logging

from .config import BAYI_IP_WHITELIST

logger = logging.getLogger(__name__)

# Redis modules (optional)
_REDIS_AVAILABLE = False
_get_bayi_whitelist = None

try:
    from services.redis.redis_bayi_whitelist import get_bayi_whitelist
    _REDIS_AVAILABLE = True
    _get_bayi_whitelist = get_bayi_whitelist
except ImportError:
    pass


def is_ip_whitelisted(client_ip: str) -> bool:
    """
    Check if client IP is in bayi IP whitelist.

    If IP is whitelisted, teachers from that IP can skip token authentication
    and gain immediate access in bayi mode.

    Uses Redis Set for multi-worker support and dynamic management.
    Falls back to in-memory set if Redis unavailable (backward compatibility).

    Args:
        client_ip: Client IP address string

    Returns:
        True if IP is whitelisted, False otherwise
    """
    # Try Redis first (for multi-worker support and dynamic management)
    if _REDIS_AVAILABLE and _get_bayi_whitelist is not None:
        try:
            whitelist = _get_bayi_whitelist()
            result = whitelist.is_ip_whitelisted(client_ip)
            if result:
                return True
        except Exception as e:
            logger.debug(
                "[Auth] Redis IP whitelist check failed, falling back to in-memory: %s",
                e
            )

    # Fallback to in-memory set (backward compatibility)
    if not BAYI_IP_WHITELIST:
        return False

    try:
        # Normalize IP address for comparison
        normalized_ip = ipaddress.ip_address(client_ip)
        ip_str = str(normalized_ip)

        # O(1) lookup in set
        if ip_str in BAYI_IP_WHITELIST:
            logger.debug(
                "IP %s matched whitelist entry (in-memory fallback)", client_ip
            )
            return True

        return False
    except ValueError:
        logger.warning("Invalid IP address format: %s", client_ip)
        return False
