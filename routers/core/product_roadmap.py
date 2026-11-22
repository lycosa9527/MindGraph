"""
Product roadmap in the shared COS folder.

Anyone can read it. Only a super admin can replace the object.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from models.domain.auth import User
from routers.auth.dependencies import require_superadmin
from services.features.roadmap.product_roadmap import (
    RoadmapWriteError,
    load_product_roadmap,
    save_product_roadmap,
)

router = APIRouter(prefix="/roadmap", tags=["Roadmap"])

RoadmapColumn = Literal["now", "next", "later", "shipped"]


class ProductRoadmapItem(BaseModel):
    """One roadmap card."""

    column: RoadmapColumn
    title: str = ""
    summary: str = ""
    owner: str = ""
    area: str = ""
    target: str = ""


class ProductRoadmapResponse(BaseModel):
    """Shared roadmap shown in the account menu."""

    updated_at: str = ""
    items: list[ProductRoadmapItem] = Field(default_factory=list)


class ProductRoadmapWrite(BaseModel):
    """Cards a super admin is saving. The server sets the date."""

    items: list[ProductRoadmapItem] = Field(default_factory=list)


@router.get("", response_model=ProductRoadmapResponse)
async def get_product_roadmap() -> ProductRoadmapResponse:
    """Return the roadmap every server reads from ``shared/roadmap/``."""
    try:
        payload = load_product_roadmap()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Could not read product roadmap") from exc
    return ProductRoadmapResponse.model_validate(payload)


@router.put("", response_model=ProductRoadmapResponse)
async def put_product_roadmap(
    body: ProductRoadmapWrite,
    _admin: User = Depends(require_superadmin),
) -> ProductRoadmapResponse:
    """Replace the shared roadmap. Only a super admin can write it."""
    rows = [item.model_dump() for item in body.items]
    try:
        payload = save_product_roadmap(rows)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid roadmap item") from exc
    except RoadmapWriteError as exc:
        raise HTTPException(status_code=503, detail="Could not save product roadmap") from exc
    return ProductRoadmapResponse.model_validate(payload)
