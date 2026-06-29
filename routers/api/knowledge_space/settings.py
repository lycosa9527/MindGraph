"""Knowledge Space settings endpoints (GET/PUT user RAG preferences)."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.requests.requests_knowledge_space import KnowledgeSpaceSettingsUpdateRequest
from models.responses import KnowledgeSpaceSettingsResponse, KnowledgeSpaceSettingsUpdateResponse
from services.knowledge.knowledge_settings import get_space_settings, update_space_settings
from services.knowledge.knowledge_space_service import KnowledgeSpaceService
from services.utils.error_types import DATABASE_ERRORS
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


def _to_response(settings) -> KnowledgeSpaceSettingsResponse:
    return KnowledgeSpaceSettingsResponse(
        default_method=settings.default_method,
        top_k=settings.top_k,
        score_threshold=settings.score_threshold,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        vector_weight=settings.vector_weight,
        keyword_weight=settings.keyword_weight,
        reranking_mode=settings.reranking_mode,
        wiki_compile_enabled=settings.wiki_compile_enabled,
        chunking_engine=settings.chunking_engine,
        has_user_overrides=settings.has_user_overrides,
    )


@router.get("/settings")
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Return effective Knowledge Space settings for the current user."""
    await KnowledgeSpaceService(db, current_user.id).create_knowledge_space()
    settings = await get_space_settings(db, current_user.id)
    return _to_response(settings)


@router.put("/settings")
async def update_settings(
    request: KnowledgeSpaceSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Persist user retrieval/chunking preferences."""
    try:
        result = await update_space_settings(
            db,
            current_user.id,
            default_method=request.default_method,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DATABASE_ERRORS as exc:
        logger.error("[KnowledgeSpace] Update settings failed for user %s: %s", current_user.id, exc)
        raise HTTPException(status_code=500, detail="Failed to update settings") from exc

    return KnowledgeSpaceSettingsUpdateResponse(
        settings=_to_response(result.settings),
        reindex_required=result.reindex_required,
    )
