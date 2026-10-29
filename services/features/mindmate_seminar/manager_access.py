"""Singleton registry for MindmateSeminarManager (leaf module; breaks import cycles).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from services.features.mindmate_seminar.manager import MindmateSeminarManager


class _MindmateSeminarManagerState:
    """Holds the process-wide MindmateSeminarManager singleton."""

    instance: Optional[MindmateSeminarManager] = None


_manager_state = _MindmateSeminarManagerState()


def register_mindmate_seminar_manager(manager: MindmateSeminarManager) -> None:
    """Register the process-wide manager instance (called from manager module init)."""
    _manager_state.instance = manager


def get_mindmate_seminar_manager() -> MindmateSeminarManager:
    """Return the registered MindmateSeminarManager singleton."""
    if _manager_state.instance is None:
        raise RuntimeError("MindmateSeminarManager has not been registered yet")
    return _manager_state.instance
