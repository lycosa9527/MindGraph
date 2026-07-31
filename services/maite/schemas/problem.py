"""
Maite problem request/response schemas.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ProblemCreate(BaseModel):
    """Create a problem from text or bank selection."""

    raw_text: str = Field(min_length=1)
    clean_text: Optional[str] = None
    source_type: str = "manual"
    subject: str = "高中数学"
    grade_level: Optional[str] = None
    topic_tags: list[str] = Field(default_factory=list)
    difficulty: Optional[str] = None
    image_url: Optional[str] = None


class ProblemRead(BaseModel):
    """Problem returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    organization_id: Optional[int] = None
    source_type: str
    raw_text: str
    clean_text: str
    image_url: Optional[str] = None
    subject: str
    grade_level: Optional[str] = None
    topic_tags: list[Any] = Field(default_factory=list)
    difficulty: Optional[str] = None
    created_at: datetime


class OcrResult(BaseModel):
    """OCR extraction result."""

    model_config = ConfigDict(extra="allow")

    raw_text: str = ""
    clean_text: str = ""
    stored_path: Optional[str] = None
    confidence: Optional[float] = None
    extra: dict[str, Any] = Field(default_factory=dict)
