"""
Mate Learning health probe.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from models.domain.auth import User
from utils.auth import get_current_user

router = APIRouter()


@router.get("/health")
async def maite_health(_current_user: User = Depends(get_current_user)) -> dict[str, str]:
    """Authenticated health probe for Mate Learning."""
    return {"status": "healthy", "service": "maite_learning"}
