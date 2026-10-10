"""
Feature Routers

Feature-specific endpoints for various application features.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from .kitty import router as kitty_router
from .library import router as library_router
from .showcase import router as showcase_router

__all__ = [
    "kitty_router",
    "library_router",
    "showcase_router",
]
