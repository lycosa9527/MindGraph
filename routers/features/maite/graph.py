"""
Mate Learning knowledge/thinking graph endpoints.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from routers.features.maite.helpers import MAITE_DOMAIN_ERRORS, raise_maite_http_error
from services.maite.domain.graph_service import GraphService
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/graph")
async def get_user_graph(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return graph node progress for the authenticated user."""
    service = GraphService(db)
    try:
        nodes = await service.list_nodes(current_user.id)
        knowledge_nodes = [node for node in nodes if node.get("graph_type") == "knowledge"]
        thinking_nodes = [node for node in nodes if node.get("graph_type") == "thinking"]
        logger.info(
            "[Maite] Graph loaded user=%s knowledge=%s thinking=%s",
            current_user.id,
            len(knowledge_nodes),
            len(thinking_nodes),
        )
        return {
            "student_id": str(current_user.id),
            "knowledge_nodes": knowledge_nodes,
            "thinking_nodes": thinking_nodes,
        }
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc
