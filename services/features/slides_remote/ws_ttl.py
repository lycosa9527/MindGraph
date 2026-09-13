"""Keep a live 演讲模式 room alive while a desktop socket is connected.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging

from services.features.slides_remote.constants import SESSION_TOUCH_SECONDS
from services.features.slides_remote.session_store import touch_session

logger = logging.getLogger(__name__)


async def run_desktop_session_touch(user_id: int, stop_event: asyncio.Event) -> None:
    """EXPIRE the Redis room until the desktop socket closes. Watch sockets skip this."""
    await touch_session(user_id)
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=SESSION_TOUCH_SECONDS)
        except TimeoutError:
            await touch_session(user_id)
        except asyncio.CancelledError:
            return
