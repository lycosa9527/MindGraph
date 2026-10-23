"""Seminar participant roles for MindMate collab groups.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

SEMINAR_ROLE_LEADER = "leader"
SEMINAR_ROLE_LEAD_PREP = "leadPrep"
SEMINAR_ROLE_CO_PREP = "coPrep"
SEMINAR_ROLE_EXPERT = "expert"
SEMINAR_ROLE_RESEARCHER = "researcher"
SEMINAR_ROLE_OBSERVER = "observer"

SEMINAR_ROLES = frozenset(
    {
        SEMINAR_ROLE_LEADER,
        SEMINAR_ROLE_LEAD_PREP,
        SEMINAR_ROLE_CO_PREP,
        SEMINAR_ROLE_EXPERT,
        SEMINAR_ROLE_RESEARCHER,
        SEMINAR_ROLE_OBSERVER,
    }
)

# Roles a leader may assign without transferring leadership.
ASSIGNABLE_SEMINAR_ROLES = frozenset(SEMINAR_ROLES - {SEMINAR_ROLE_LEADER})
# Leader may also assign leader (transfers the role).
LEADER_ASSIGNABLE_SEMINAR_ROLES = frozenset(SEMINAR_ROLES)


def normalize_seminar_role(raw: str | None, *, default: str = SEMINAR_ROLE_OBSERVER) -> str:
    """Return a known seminar role or the default."""
    role = (raw or "").strip()
    if role in SEMINAR_ROLES:
        return role
    return default


def resolve_seminar_leader_id(
    roles_by_user: dict[int, str],
    owner_user_id: int,
) -> int:
    """Return the current seminar leader, falling back to the session owner."""
    for user_id, role in roles_by_user.items():
        if role == SEMINAR_ROLE_LEADER:
            return int(user_id)
    return int(owner_user_id)
