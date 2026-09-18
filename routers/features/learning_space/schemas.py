"""Pydantic schemas for Learning Space APIs.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

_CLASS_CODE_RE = re.compile(r"^[A-Za-z0-9]{4,16}$")


class PilotTeacherCreate(BaseModel):
    """Grant Learning Space to a teacher."""

    teacher_user_id: int
    organization_id: int


class ClassCreate(BaseModel):
    """Create a learning class."""

    name: str = Field(..., min_length=1, max_length=100)
    teacher_user_id: int
    max_students: int = Field(default=60, ge=1, le=200)


class ClassUpdate(BaseModel):
    """Patch class fields."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    status: Optional[str] = None
    max_students: Optional[int] = Field(None, ge=1, le=200)
    class_code: Optional[str] = Field(None, min_length=4, max_length=16)
    assistant_user_ids: Optional[list[int]] = None

    @field_validator("class_code")
    @classmethod
    def class_code_must_be_alnum(cls, value: Optional[str]) -> Optional[str]:
        """Require 4–16 letters/digits; normalize to uppercase."""
        if value is None:
            return None
        code = value.strip()
        if not _CLASS_CODE_RE.fullmatch(code):
            raise ValueError("class_code must be 4-16 alphanumeric characters")
        return code.upper()


class StudentImportRequest(BaseModel):
    """Import student names into a class."""

    names: list[str] = Field(..., min_length=1, max_length=200)


class AccountImportRequest(BaseModel):
    """Import existing registered accounts into a class by phone."""

    phones: list[str] = Field(..., min_length=1, max_length=200)


class AssignmentCreate(BaseModel):
    """Teacher creates homework."""

    class_id: int
    title: str = Field(..., min_length=1, max_length=200)
    instructions: str = ""
    template_diagram_id: str = Field(..., min_length=1, max_length=36)
    due_at: Optional[datetime] = None
    ai_permissions: dict[str, Any] = Field(default_factory=dict)
    instruction_images: list[str] = Field(default_factory=list, max_length=6)
    status: str = "active"

    @field_validator("status")
    @classmethod
    def status_allowed(cls, value: str) -> str:
        """Only active or draft on create."""
        normalized = (value or "active").strip().lower()
        if normalized not in {"active", "draft"}:
            raise ValueError("status must be active or draft")
        return normalized

    @field_validator("instruction_images")
    @classmethod
    def instruction_images_size(cls, value: list[str]) -> list[str]:
        """Keep instruction image payloads small (data URLs or short URLs)."""
        cleaned: list[str] = []
        for raw in value:
            item = (raw or "").strip()
            if not item:
                continue
            if len(item) > 200_000:
                raise ValueError("instruction image too large")
            cleaned.append(item)
            if len(cleaned) >= 6:
                break
        return cleaned


class DraftDiagramBindRequest(BaseModel):
    """Bind a student-owned library diagram as the homework draft."""

    diagram_id: str = Field(..., min_length=1, max_length=36)


class ExtendDueRequest(BaseModel):
    """Per-student due date override."""

    due_at: datetime


class SubmissionReviewRequest(BaseModel):
    """Teacher review / rubric for a submission."""

    scores: dict[str, int] = Field(default_factory=dict)
    comment: str = ""
    liked: bool = False
    pinned: bool = False


class StudentChangePasswordRequest(BaseModel):
    """Student forced password change."""

    new_password: str = Field(..., min_length=6, max_length=128)


class StudentLoginRequest(BaseModel):
    """Class-code student login."""

    class_code: str = Field(..., min_length=4, max_length=16)
    name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=128)
    captcha: str = Field(..., min_length=4, max_length=4)
    captcha_id: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "class_code": "AB12CD",
                "name": "张三",
                "password": "zs123",
                "captcha": "AB12",
                "captcha_id": "uuid",
            }
        }
    )
