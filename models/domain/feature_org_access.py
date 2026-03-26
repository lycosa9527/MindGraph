"""Pydantic models for per-feature organization/user access rules."""

from pydantic import BaseModel, Field


class FeatureOrgAccessEntry(BaseModel):
    """Access rule for one feature flag (client API key, e.g. feature_workshop_chat)."""

    restrict: bool = False
    organization_ids: list[int] = Field(default_factory=list)
    user_ids: list[int] = Field(default_factory=list)
