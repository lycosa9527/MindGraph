"""Teardown helpers for Kitty session event buses (no command-router imports).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from services.kitty.omni.context_refresh import cancel_pending_omni_refresh
from services.kitty.session.events import get_session_event_bus, remove_session_event_bus
from services.kitty.session.memory import remove_session_memory


async def teardown_session_event_handlers(voice_session_id: str) -> None:
    """Teardown session event handlers."""
    bus = get_session_event_bus(voice_session_id)
    await bus.stop()
    remove_session_event_bus(voice_session_id)
    remove_session_memory(voice_session_id)
    cancel_pending_omni_refresh(voice_session_id)
