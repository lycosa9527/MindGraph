"""Shared Kitty control Redis channel helpers (no dispatch side effects).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os
import socket

KITTY_CONTROL_PAYLOAD_VERSION = 1


def kitty_control_channel() -> str:
    """Redis pub/sub channel for Kitty control messages (override via env)."""
    return os.getenv("KITTY_CONTROL_CHANNEL", "mg:kitty:control").strip() or "mg:kitty:control"


def get_kitty_control_instance_id() -> str:
    """
    Per-process instance tag used to skip local subscriber handling for
    handshake preemption (same worker already runs the in-process lock path).
    """
    explicit = os.getenv("KITTY_CONTROL_INSTANCE_ID", "").strip()
    if explicit:
        return explicit[:128]
    hn = socket.gethostname()
    return f"{hn}:{os.getpid()}"[:128]
