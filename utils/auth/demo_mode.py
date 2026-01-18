"""
Demo Mode Authentication for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Demo mode passkey verification functions.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from .config import AUTH_MODE, DEMO_PASSKEY, ADMIN_DEMO_PASSKEY, PUBLIC_DASHBOARD_PASSKEY

logger = logging.getLogger(__name__)


def display_demo_info() -> None:
    """Display demo mode information on startup"""
    if AUTH_MODE == "demo":
        logger.info("=" * 60)
        logger.info("DEMO MODE ACTIVE")
        logger.info("Passkey: %s", DEMO_PASSKEY)
        logger.info("Passkey length: %d characters", len(DEMO_PASSKEY))
        logger.info("Access: /demo")
        logger.info("=" * 60)


def verify_demo_passkey(passkey: str) -> bool:
    """
    Verify demo passkey (regular or admin)

    Args:
        passkey: Passkey string to verify

    Returns:
        True if valid, False otherwise
    """
    # Strip whitespace from input passkey to handle client-side issues
    passkey = passkey.strip() if passkey else ""
    return passkey in [DEMO_PASSKEY, ADMIN_DEMO_PASSKEY]


def is_admin_demo_passkey(passkey: str) -> bool:
    """
    Check if passkey is for admin demo access

    Args:
        passkey: Passkey string to check

    Returns:
        True if admin passkey, False otherwise
    """
    # Strip whitespace from input passkey to handle client-side issues
    passkey = passkey.strip() if passkey else ""
    return passkey == ADMIN_DEMO_PASSKEY


def verify_dashboard_passkey(passkey: str) -> bool:
    """
    Verify public dashboard passkey

    Args:
        passkey: Passkey string to verify

    Returns:
        True if valid, False otherwise
    """
    # Strip whitespace from input passkey to handle client-side issues
    passkey = passkey.strip() if passkey else ""
    return passkey == PUBLIC_DASHBOARD_PASSKEY
