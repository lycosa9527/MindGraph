"""Singleton registry for MindmateCollabManager (leaf module; breaks import cycles).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from services.features.mindmate_collab.manager import MindmateCollabManager


class _MindmateCollabManagerState:
    """Holds the process-wide MindmateCollabManager singleton."""

    instance: Optional[MindmateCollabManager] = None


_manager_state = _MindmateCollabManagerState()


def register_mindmate_collab_manager(manager: MindmateCollabManager) -> None:
    """Register the process-wide manager instance (called from manager module init)."""
    _manager_state.instance = manager


def get_mindmate_collab_manager() -> MindmateCollabManager:
    """Return the registered MindmateCollabManager singleton."""
    if _manager_state.instance is None:
        raise RuntimeError("MindmateCollabManager has not been registered yet")
    return _manager_state.instance
