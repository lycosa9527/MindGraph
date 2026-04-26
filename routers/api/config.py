"""
Config API Router
================

Provides configuration and feature flags to the frontend.
"""

import os
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from config.settings import config
from models.domain.auth import User
from models.domain.feature_org_access import FeatureOrgAccessEntry
from routers.api.helpers import normalize_external_base_url
from routers.auth.dependencies import get_current_user_optional
from services.feature_access.repository import load_feature_org_access_map
from utils.auth.roles import is_admin

router = APIRouter(prefix="/config", tags=["config"])


def _sanitize_feature_org_access_map(
    user: User,
    full_map: dict[str, FeatureOrgAccessEntry],
) -> dict[str, FeatureOrgAccessEntry]:
    """
    Strip other tenants' ids from allowlists before sending flags to non-admins.

    The client still evaluates ``restrict`` plus whether *this* user's org/user id
    appears granted; it must not receive full org/user enumerations from Postgres.
    """
    if is_admin(user):
        return full_map
    uid = getattr(user, "id", None)
    oid = getattr(user, "organization_id", None)
    out: dict[str, FeatureOrgAccessEntry] = {}
    for key, entry in full_map.items():
        org_ids = [x for x in entry.organization_ids if oid is not None and int(x) == int(oid)]
        user_ids = [x for x in entry.user_ids if uid is not None and int(x) == int(uid)]
        out[key] = FeatureOrgAccessEntry(
            restrict=entry.restrict,
            organization_ids=org_ids,
            user_ids=user_ids,
        )
    return out


class FeatureFlagsResponse(BaseModel):
    """Feature flags response model."""

    external_base_url: str
    feature_rag_chunk_test: bool
    feature_course: bool
    feature_template: bool
    feature_community: bool
    feature_askonce: bool
    feature_school_zone: bool
    feature_debateverse: bool
    feature_knowledge_space: bool
    feature_library: bool
    feature_gewe: bool
    feature_smart_response: bool
    feature_teacher_usage: bool
    feature_workshop_chat: bool
    feature_markets: bool
    feature_mindbot: bool
    workshop_chat_preview_org_ids: list[int]
    feature_org_access: dict[str, FeatureOrgAccessEntry] = Field(default_factory=dict)


@router.get("/features", response_model=FeatureFlagsResponse)
async def get_feature_flags(
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get feature flags configuration.

    ``feature_org_access`` is omitted for anonymous requests. Authenticated
    non-admins receive allowlist entries with only their own organization id and/or
    user id (when present in the stored rules) so other schools' grants are not
    exposed. Admins receive the full map (e.g. Admin Features tab).
    """
    env_base = os.getenv("EXTERNAL_BASE_URL", "")
    external_base = normalize_external_base_url(env_base)
    raw_access = await load_feature_org_access_map() if current_user is not None else {}
    access_map = _sanitize_feature_org_access_map(current_user, raw_access) if current_user is not None else {}
    return FeatureFlagsResponse(
        external_base_url=external_base,
        feature_rag_chunk_test=config.FEATURE_RAG_CHUNK_TEST,
        feature_course=config.FEATURE_COURSE,
        feature_template=config.FEATURE_TEMPLATE,
        feature_community=config.FEATURE_COMMUNITY,
        feature_askonce=config.FEATURE_ASKONCE,
        feature_school_zone=config.FEATURE_SCHOOL_ZONE,
        feature_debateverse=config.FEATURE_DEBATEVERSE,
        feature_knowledge_space=config.FEATURE_KNOWLEDGE_SPACE,
        feature_library=config.FEATURE_LIBRARY,
        feature_gewe=config.FEATURE_GEWE,
        feature_smart_response=config.FEATURE_SMART_RESPONSE,
        feature_teacher_usage=config.FEATURE_TEACHER_USAGE,
        feature_workshop_chat=config.FEATURE_WORKSHOP_CHAT,
        feature_markets=config.FEATURE_MARKETS,
        feature_mindbot=config.FEATURE_MINDBOT,
        workshop_chat_preview_org_ids=sorted(config.WORKSHOP_CHAT_PREVIEW_ORG_IDS),
        feature_org_access=access_map,
    )
