"""
Workshop Chat Request Schemas
================================

Pydantic models for request validation, extracted from the router layer
following Zulip's pattern of separating schema definitions from view logic.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class OrgMemberRow(BaseModel):
    """One organization member for roster / presence / @mention."""

    id: int
    name: str
    avatar: Optional[str] = None
    last_seen_at: Optional[datetime] = None


class OrgMembersPage(BaseModel):
    """Paginated org roster (contacts sidebar, mention search)."""

    items: List[OrgMemberRow]
    total: int
    limit: int
    offset: int


class CreateChannelRequest(BaseModel):
    """Request body for creating a channel (group or lesson-study)."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    avatar: Optional[str] = Field(None, max_length=50)
    parent_id: Optional[int] = None
    color: Optional[str] = Field(None, max_length=10)
    status: Optional[str] = Field(None, max_length=20)
    deadline: Optional[datetime] = None
    diagram_id: Optional[str] = None


class UpdateChannelRequest(BaseModel):
    """Request body for updating a channel."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    avatar: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, max_length=10)
    status: Optional[str] = Field(None, max_length=20)
    deadline: Optional[datetime] = None
    diagram_id: Optional[str] = None
    is_resolved: Optional[bool] = None


class CreateTopicRequest(BaseModel):
    """Request body for creating a topic (lightweight conversation)."""

    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)


class UpdateTopicRequest(BaseModel):
    """Request body for updating a topic."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)


class SendMessageRequest(BaseModel):
    """Request body for sending a message."""

    content: str = Field(..., min_length=1, max_length=5000)
    message_type: str = "text"
    parent_id: Optional[int] = None


class EditMessageRequest(BaseModel):
    """Request body for editing a message."""

    content: str = Field(..., min_length=1, max_length=5000)


class SendDMRequest(BaseModel):
    """Request body for sending a direct message."""

    content: str = Field(..., min_length=1, max_length=5000)
    message_type: str = "text"


# ── Channel settings / preferences ──────────────────────────────


class UpdateMemberPrefsRequest(BaseModel):
    """Request body for updating per-user channel subscription prefs."""

    color: Optional[str] = Field(None, max_length=10)
    desktop_notifications: Optional[bool] = None
    email_notifications: Optional[bool] = None


class UpdateChannelPermissionsRequest(BaseModel):
    """Request body for updating channel-level settings."""

    channel_type: Optional[str] = Field(None, max_length=20)
    posting_policy: Optional[str] = Field(None, max_length=20)
    is_default: Optional[bool] = None


class ReorderTeachingGroupsRequest(BaseModel):
    """Ordered list of top-level teaching group channel IDs (same org)."""

    channel_ids: List[int] = Field(..., min_length=1)


class InviteChannelMemberRequest(BaseModel):
    """Add an org colleague to a channel (manager invite)."""

    user_id: int = Field(..., ge=1)


# ── Topic settings ───────────────────────────────────────────────


class MoveTopicRequest(BaseModel):
    """Request body for moving a topic to another channel."""

    target_channel_id: int


class RenameTopicRequest(BaseModel):
    """Request body for renaming a topic."""

    title: str = Field(..., min_length=1, max_length=200)


class SetTopicVisibilityRequest(BaseModel):
    """Request body for setting user topic visibility."""

    visibility_policy: str = Field(..., max_length=20)
