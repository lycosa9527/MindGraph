"""
Maite mentor request/response schemas.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Union

from pydantic import BaseModel, ConfigDict, Field


class MentorDecomposeInput(BaseModel):
    """Input for initial reverse-decompose mentor call."""

    question: str = Field(min_length=1)


class MentorDecomposeOutput(BaseModel):
    """Flexible decompose tables returned by the mentor."""

    model_config = ConfigDict(extra="allow")

    condition_table: list[Union[dict[str, Any], str]] = Field(default_factory=list)
    step_table: list[Union[dict[str, Any], str]] = Field(default_factory=list)
    model_table: list[Union[dict[str, Any], str]] = Field(default_factory=list)
    next_question: str = ""
    opening_guidance: str = ""


class MentorFollowUpInput(BaseModel):
    """Input for mentor follow-up conversation."""

    question: str = Field(min_length=1)
    reply: str = Field(min_length=1)
    history: list[dict[str, Any]] = Field(default_factory=list)


class MentorFollowUpOutput(BaseModel):
    """Mentor follow-up reply with optional guiding question."""

    reply: str
    guiding_question: str = ""
