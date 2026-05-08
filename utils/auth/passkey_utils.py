"""
Shared 6-digit passkey checks (Bayi fallback login, public dashboard).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from . import config


def verify_bayi_passkey(passkey: str) -> bool:
    """Return True if ``passkey`` matches configured Bayi passkey (ADMIN_PHONES grants admin)."""
    normalized = passkey.strip() if passkey else ""
    return normalized == config.BAYI_PASSKEY


def verify_dashboard_passkey(passkey: str) -> bool:
    """Return True if ``passkey`` matches the public dashboard passkey."""
    normalized = passkey.strip() if passkey else ""
    return normalized == config.PUBLIC_DASHBOARD_PASSKEY
