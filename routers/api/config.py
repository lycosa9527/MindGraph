"""
Config API Router
================

Provides configuration and feature flags to the frontend.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from config.settings import config

router = APIRouter(prefix="/config", tags=["config"])


class FeatureFlagsResponse(BaseModel):
    """Feature flags response model."""
    feature_rag_chunk_test: bool


@router.get("/features", response_model=FeatureFlagsResponse)
async def get_feature_flags():
    """Get feature flags configuration."""
    return FeatureFlagsResponse(
        feature_rag_chunk_test=config.FEATURE_RAG_CHUNK_TEST
    )
