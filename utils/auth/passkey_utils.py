"""
Shared 6-digit passkey checks (Bayi fallback login).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import hmac

from . import config


def verify_bayi_passkey(passkey: str) -> bool:
    """Return True if ``passkey`` matches configured Bayi passkey (ADMIN_PHONES grants admin)."""
    normalized = passkey.strip() if passkey else ""
    if not normalized or not config.BAYI_PASSKEY:
        return False
    return hmac.compare_digest(normalized, config.BAYI_PASSKEY)
