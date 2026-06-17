"""
Pydantic models for per-feature organization/user access rules.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from pydantic import BaseModel, Field


class FeatureOrgAccessEntry(BaseModel):
    """Access rule for one feature flag (client API key, e.g. feature_workshop_chat)."""

    restrict: bool = False
    organization_ids: list[int] = Field(default_factory=list)
    user_ids: list[int] = Field(default_factory=list)
