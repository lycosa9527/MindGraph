"""
Market router helpers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from fastapi import HTTPException, status

from config.settings import config


def require_markets_enabled() -> None:
    """Raise 404 if markets feature is disabled (avoid advertising existence)."""
    if not config.FEATURE_MARKETS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
