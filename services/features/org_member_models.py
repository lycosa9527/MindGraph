"""
Org roster rows shared by chat, collab, and library share.

Kept out of the workshop-chat router package so roster queries can load
without pulling that package's ``__init__`` (which imports the roster).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OrgMemberRow(BaseModel):
    """One organization member for roster / presence / @mention."""

    id: int
    name: str
    avatar: Optional[str] = None
    last_seen_at: Optional[datetime] = None


class OrgMembersPage(BaseModel):
    """Paginated org roster (contacts sidebar, mention search)."""

    items: list[OrgMemberRow]
    total: int
    limit: int
    offset: int
