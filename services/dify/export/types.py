"""
Shared MindMate export datatypes (breaks collect/target import cycles).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, List, Literal, Optional, Union

ExportScope = Literal["all", "whole", "users"]

ControlCallback = Callable[[], Union[bool, Awaitable[bool]]]
ProgressCallback = Callable[[str, int, int, Dict[str, object]], bool]


@dataclass(frozen=True)
class UserTarget:
    """One Dify ``user`` identity to export (web MindMate or DingTalk MindBot)."""

    organization_id: int
    user_id: Optional[int]
    dify_user: str
    label: str
    channel: str = "web"


@dataclass
class TargetFetchResult:
    """Structured per-endpoint fetch outcome for verification."""

    dify_user: str
    endpoint_source: str
    server: int
    organization_id: int
    channel: str
    conversations_fetched: int = 0
    pagination_complete: bool = True
    fetch_errors: List[str] = field(default_factory=list)
    messages_by_conv_id: Dict[str, bool] = field(default_factory=dict)
