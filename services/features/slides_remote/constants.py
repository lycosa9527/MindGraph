"""
Constants for the mind-map slide remote.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Final

STATE_IDLE: Final[str] = "idle"
STATE_LIVE: Final[str] = "live"
STATE_ENDED: Final[str] = "ended"

SESSION_TTL_SECONDS: Final[int] = 120
COMMAND_QUEUE_MAX: Final[int] = 8
TITLE_MAX: Final[int] = 80
DIAGRAM_ID_MAX: Final[int] = 64

USER_KEY: Final[str] = "slide_remote:user:{user_id}"
COMMAND_KEY: Final[str] = "slide_remote:user:{user_id}:cmds"

TRAVERSAL_MODES: frozenset[str] = frozenset({"firstLevel", "deep"})
COMMAND_ACTIONS: frozenset[str] = frozenset(
    {"next", "prev", "autoplay", "traversal", "quit", "start"}
)
