"""Singleton registry for OnlineCollabManager (leaf module; breaks import cycles).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from services.online_collab.core.online_collab_manager import OnlineCollabManager


class _OnlineCollabManagerState:
    """Holds the process-wide OnlineCollabManager singleton."""

    instance: Optional[OnlineCollabManager] = None


_manager_state = _OnlineCollabManagerState()


def register_online_collab_manager(manager: OnlineCollabManager) -> None:
    """Register the process-wide manager instance (called from manager module init)."""
    _manager_state.instance = manager


def get_online_collab_manager() -> OnlineCollabManager:
    """Return the registered OnlineCollabManager singleton."""
    if _manager_state.instance is None:
        raise RuntimeError("OnlineCollabManager has not been registered yet")
    return _manager_state.instance
