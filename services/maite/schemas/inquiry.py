"""
Maite inquiry session schemas.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    """Start a new inquiry session."""

    problem_id: int
    mode: str = "inquiry"
    title: Optional[str] = None


class SessionRead(BaseModel):
    """Session summary for list/detail views."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    organization_id: Optional[int] = None
    problem_id: int
    status: str
    current_stage: str
    mode: str
    title: Optional[str] = None
    version_no: int = 1
    original_session_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class SnapshotRead(BaseModel):
    """Flexible session snapshot aggregating stage artifacts."""

    model_config = ConfigDict(extra="allow")

    session: dict[str, Any] = Field(default_factory=dict)
    problem: Optional[dict[str, Any]] = None
    decompose: Optional[dict[str, Any]] = None
    diagnosis: Optional[dict[str, Any]] = None
    remedy_tasks: list[dict[str, Any]] = Field(default_factory=list)
    variant_tasks: list[dict[str, Any]] = Field(default_factory=list)
    report: Optional[dict[str, Any]] = None
