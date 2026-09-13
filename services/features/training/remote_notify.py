"""SSE doorbell plus watch WebSocket snapshot after a training write.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Optional

from services.features.training.constants import STATE_ENDED
from services.features.training.payloads import snapshot_from_session
from services.features.training.sse import publish_event
from services.features.training.wake_fanout import publish_training_snapshot_view


async def notify_training_session_changed(org_id: int, session: Optional[dict[str, Any]]) -> None:
    """Publish the seq doorbell and the watch HUD snapshot."""
    event = "ended" if session and session.get("state") == STATE_ENDED else "seq"
    seq = int((session or {}).get("seq") or 0)
    await publish_event(org_id, event, {"seq": seq})
    view = snapshot_from_session(session)
    instructor_raw = (session or {}).get("instructor_id")
    instructor_id: Optional[int]
    try:
        instructor_id = int(instructor_raw) if instructor_raw is not None else None
    except (TypeError, ValueError):
        instructor_id = None
    await publish_training_snapshot_view(org_id, view, instructor_id=instructor_id)
