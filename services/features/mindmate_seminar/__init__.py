"""
MindMate collab package exports.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from services.features.mindmate_seminar.idle_monitor import start_mindmate_seminar_idle_monitor
from services.features.mindmate_seminar.manager import MindmateSeminarManager
from services.features.mindmate_seminar.manager_access import (
    get_mindmate_seminar_manager,
    register_mindmate_seminar_manager,
)

register_mindmate_seminar_manager(MindmateSeminarManager())

__all__ = [
    "MindmateSeminarManager",
    "get_mindmate_seminar_manager",
    "start_mindmate_seminar_idle_monitor",
]
