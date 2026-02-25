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
    feature_course: bool
    feature_template: bool
    feature_community: bool
    feature_askonce: bool
    feature_school_zone: bool
    feature_debateverse: bool
    feature_knowledge_space: bool
    feature_library: bool
    feature_smart_response: bool
    feature_teacher_usage: bool


@router.get("/features", response_model=FeatureFlagsResponse)
async def get_feature_flags():
    """Get feature flags configuration."""
    return FeatureFlagsResponse(
        feature_rag_chunk_test=config.FEATURE_RAG_CHUNK_TEST,
        feature_course=config.FEATURE_COURSE,
        feature_template=config.FEATURE_TEMPLATE,
        feature_community=config.FEATURE_COMMUNITY,
        feature_askonce=config.FEATURE_ASKONCE,
        feature_school_zone=config.FEATURE_SCHOOL_ZONE,
        feature_debateverse=config.FEATURE_DEBATEVERSE,
        feature_knowledge_space=config.FEATURE_KNOWLEDGE_SPACE,
        feature_library=config.FEATURE_LIBRARY,
        feature_smart_response=config.FEATURE_SMART_RESPONSE,
        feature_teacher_usage=config.FEATURE_TEACHER_USAGE,
    )
