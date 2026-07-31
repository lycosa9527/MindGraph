"""
Mate Learning API router package.

Chinese name: 迈特学习法
English name: Mate Learning

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from fastapi import APIRouter

from routers.features.maite import (
    diagnosis,
    graph,
    health,
    inquiry,
    mentor,
    problems,
    remedy,
    reports,
    variants,
)

router = APIRouter(prefix="/api/maite", tags=["Mate Learning"])

router.include_router(health.router)
router.include_router(problems.router)
router.include_router(mentor.router)
router.include_router(inquiry.router)
router.include_router(diagnosis.router)
router.include_router(remedy.router)
router.include_router(variants.router)
router.include_router(reports.router)
router.include_router(graph.router)

__all__ = ["router"]
