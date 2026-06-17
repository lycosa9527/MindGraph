"""Validate/normalize Kitty WebSocket path segment ``diagram_session_id`` (Redis + in-memory scope).

Production rules
----------------
- One active Kitty WebSocket + voice stack per normalized scope id on a given worker
  (see ``diagram_session_voice_lock`` + ``active_websockets``).
- Mobile and desktop **share** the scope when bound to a **library diagram**: use the
  saved diagram UUID as ``diagram_session_id`` so ``kitty:sessionmeta`` / ``live_spec``
  align and ``GET /api/kitty/mobile_lane`` reflects an open mobile session.
- **Ephemeral** scopes (unsaved canvas / mobile hub without library row) use a random
  client-generated id; only that client should hit that path until persisted.

Library diagram ids are UUID-like ASCII strings; reject odd characters and length to
avoid Redis key abuse and lock map growth attacks.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Optional

MAX_KITTY_WS_SCOPE_LEN = 128
_SCOPE_SAFE = re.compile(r"^[0-9a-zA-Z_-]+$")


def normalize_kitty_diagram_session_id(raw: Optional[str]) -> Optional[str]:
    """
    Return a safe scope string or ``None`` if ``raw`` is unusable.

    Allowed: ASCII letters, digits, hyphen, underscore; length 1..128 after strip.
    """
    if raw is None or not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s or len(s) > MAX_KITTY_WS_SCOPE_LEN:
        return None
    if not _SCOPE_SAFE.match(s):
        return None
    return s
