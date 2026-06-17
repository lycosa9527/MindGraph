"""
Shared FastAPI router and in-memory voice session state.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from fastapi import APIRouter

from services.kitty.session.runtime_state import active_websockets, logger, voice_sessions

router = APIRouter()

__all__ = [
    "active_websockets",
    "logger",
    "router",
    "voice_sessions",
]
