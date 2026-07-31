"""
Maite Learning health endpoints.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def maite_health() -> dict[str, str]:
    """Lightweight health probe for Maite Learning."""
    return {"status": "healthy", "service": "maite_learning"}
