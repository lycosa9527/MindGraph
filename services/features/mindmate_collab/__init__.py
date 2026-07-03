"""
MindMate collab package exports.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from services.features.mindmate_collab.idle_monitor import start_mindmate_collab_idle_monitor
from services.features.mindmate_collab.manager import MindmateCollabManager
from services.features.mindmate_collab.manager_access import (
    get_mindmate_collab_manager,
    register_mindmate_collab_manager,
)

register_mindmate_collab_manager(MindmateCollabManager())

__all__ = [
    "MindmateCollabManager",
    "get_mindmate_collab_manager",
    "start_mindmate_collab_idle_monitor",
]
