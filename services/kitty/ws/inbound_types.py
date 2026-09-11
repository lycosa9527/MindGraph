"""Shared types for Kitty WebSocket inbound dispatch.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from fastapi import WebSocket

from models.domain.auth import User

KittyInboundFlow = Literal["continue", "stop"]


@dataclass(slots=True)
class KittyWsInboundContext:
    """Per-connection state required to dispatch one client JSON message."""

    websocket: WebSocket
    current_user: User
    diagram_session_id: str
    voice_session_id: str
    hub_session_id: str
    hub: Any
    agent_session_id: str
    user_id: str
