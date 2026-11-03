"""
Knowledge Space Debug Router
=============================

Personal knowledge no longer has a local vector database to inspect.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from fastapi import APIRouter, Depends, HTTPException

from models.domain.auth import User
from utils.auth import get_current_user

router = APIRouter()


@router.get("/metrics/compression")
async def get_compression_metrics(current_user: User = Depends(get_current_user)):
    """Personal knowledge does not compress a local vector collection."""
    raise HTTPException(
        status_code=410,
        detail=f"Personal knowledge for user {current_user.id} does not use a local vector store",
    )


@router.get("/debug/qdrant-diagnostics")
async def get_qdrant_diagnostics(current_user: User = Depends(get_current_user)):
    """Personal knowledge does not keep a local vector collection."""
    raise HTTPException(
        status_code=410,
        detail=f"Personal knowledge for user {current_user.id} does not use a local vector store",
    )
