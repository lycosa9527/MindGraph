"""Kitty Session Manager package — alignment, WS pairing leases, action journal.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from services.kitty.session.manager.align import (
    build_kitty_session_snapshot,
    require_aligned_for_verified_edit,
    resolve_promote_target,
)
from services.kitty.session.manager.api import KittySessionManager, get_kitty_session_manager
from services.kitty.session.manager.types import (
    KittyAlignResult,
    KittyAlignment,
    KittyIngressOwner,
    KittyJournalEvent,
    KittySessionSnapshot,
)

__all__ = [
    "KittyAlignResult",
    "KittyAlignment",
    "KittyIngressOwner",
    "KittyJournalEvent",
    "KittySessionManager",
    "KittySessionSnapshot",
    "build_kitty_session_snapshot",
    "get_kitty_session_manager",
    "require_aligned_for_verified_edit",
    "resolve_promote_target",
]
