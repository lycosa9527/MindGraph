"""Direct voice session dict lookups without lifecycle side effects.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.kitty.session.runtime_state import voice_sessions


def lookup_voice_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Return the live voice session record, if present."""
    return voice_sessions.get(session_id)
