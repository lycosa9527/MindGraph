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
# A colleague who walked into an open school seminar has no assigned seat.
SEMINAR_ROLE_UNASSIGNED = "none"

SEMINAR_ROLES = frozenset(
    {
        SEMINAR_ROLE_LEADER,
        SEMINAR_ROLE_LEAD_PREP,
        SEMINAR_ROLE_CO_PREP,
        SEMINAR_ROLE_EXPERT,
        SEMINAR_ROLE_RESEARCHER,
        SEMINAR_ROLE_OBSERVER,
        SEMINAR_ROLE_UNASSIGNED,
    }
)

# Roles a leader may assign without transferring leadership.
ASSIGNABLE_SEMINAR_ROLES = frozenset(SEMINAR_ROLES - {SEMINAR_ROLE_LEADER, SEMINAR_ROLE_UNASSIGNED})
# Leader may also assign leader (transfers the role). Unassigned is not a seat they pick.
LEADER_ASSIGNABLE_SEMINAR_ROLES = frozenset(SEMINAR_ROLES - {SEMINAR_ROLE_UNASSIGNED})

# Matches mindmate_seminar_members.seminar_role String(32).
SEMINAR_CUSTOM_ROLE_MAX = 32


def is_builtin_seminar_role(role: str) -> bool:
    """True when the role is one of the fixed seminar seats."""
    return role in SEMINAR_ROLES


def is_custom_seminar_role(role: str) -> bool:
    """True when the leader typed a free-text role label."""
    cleaned = role.strip()
    if not cleaned or cleaned in SEMINAR_ROLES:
        return False
    if len(cleaned) > SEMINAR_CUSTOM_ROLE_MAX:
        return False
    return all(ch.isprintable() and ch not in "\n\r\t" for ch in cleaned)


def is_leader_assignable_seminar_role(role: str) -> bool:
    """True when a leader may assign this role to another member."""
    return role in LEADER_ASSIGNABLE_SEMINAR_ROLES or is_custom_seminar_role(role)


def normalize_seminar_role(raw: str | None, *, default: str = SEMINAR_ROLE_OBSERVER) -> str:
    """Return a known seminar role, a sanitized custom label, or the default."""
    role = (raw or "").strip()
    if role in SEMINAR_ROLES:
        return role
    if is_custom_seminar_role(role):
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
