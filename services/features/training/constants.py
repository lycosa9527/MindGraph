"""
Constants for org training follow.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Final

STATE_LIVE: Final[str] = "live"
STATE_PAUSED: Final[str] = "paused"
STATE_ENDED: Final[str] = "ended"
STATE_NONE: Final[str] = "none"

ACTIVE_STATES: frozenset[str] = frozenset({STATE_LIVE, STATE_PAUSED})

SESSION_HARD_TTL_SECONDS: Final[int] = 4 * 60 * 60
TOMBSTONE_TTL_SECONDS: Final[int] = 60
INSTRUCTOR_HEARTBEAT_STALE_SECONDS: Final[int] = 3 * 60
ACTIVITY_TTL_SECONDS: Final[int] = 45
STEER_MIN_INTERVAL_SECONDS: Final[float] = 0.5
MAX_TOPIC_OPTIONS: Final[int] = 20
MAX_OPTION_LABEL_LEN: Final[int] = 80
ROSTER_PAGE_MAX: Final[int] = 50

ORG_SESSION_KEY: Final[str] = "training:org:{org_id}"
INSTRUCTOR_KEY: Final[str] = "training:instructor:{user_id}"
ACTIVITY_KEY: Final[str] = "training:org:{org_id}:activity"
EVENTS_CHANNEL: Final[str] = "training:org:{org_id}:events"

VALID_DIAGRAM_TYPES: frozenset[str] = frozenset(
    {
        "circle_map",
        "bubble_map",
        "double_bubble_map",
        "tree_map",
        "brace_map",
        "flow_map",
        "multi_flow_map",
        "bridge_map",
        "mindmap",
        "mind_map",
        "concept_map",
    }
)

GENERATE_STATES: frozenset[str] = frozenset({"idle", "generating", "done"})
