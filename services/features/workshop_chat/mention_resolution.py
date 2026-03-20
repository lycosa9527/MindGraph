"""
Workshop chat @**Display Name** mention resolution.

Valid targets:
- Users in the effective organization (channel org, else sender org).
- Users with role ``admin`` (platform / support), any org, name match.
- Optional extra user IDs from env ``WORKSHOP_MENTIONABLE_STAFF_USER_IDS``
  (comma-separated), name must still match.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os
import re
from typing import FrozenSet, List, Optional, Sequence, Set

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from models.domain.auth import User

_MENTION_RE = re.compile(r"@\*\*([^*]+)\*\*")


class MentionResolutionError(Exception):
    """Raised when message content contains invalid or ambiguous mentions."""

    def __init__(
        self,
        unknown_names: Sequence[str],
        ambiguous_names: Sequence[str],
    ) -> None:
        self.unknown_names = list(unknown_names)
        self.ambiguous_names = list(ambiguous_names)
        super().__init__(
            f"unknown={self.unknown_names!r}, ambiguous={self.ambiguous_names!r}"
        )


def parse_mention_display_names(content: str) -> List[str]:
    """Return unique display names from @**Name** tokens, in first-seen order."""
    seen: Set[str] = set()
    ordered: List[str] = []
    for match in _MENTION_RE.finditer(content):
        inner = match.group(1).strip()
        if not inner or inner in seen:
            continue
        seen.add(inner)
        ordered.append(inner)
    return ordered


def _staff_id_set() -> FrozenSet[int]:
    raw = os.getenv("WORKSHOP_MENTIONABLE_STAFF_USER_IDS", "")
    found: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            found.append(int(part))
    return frozenset(found)


def _users_matching_mention(
    db: Session,
    lowered: str,
    effective_org_id: Optional[int],
    staff_ids: FrozenSet[int],
) -> List[User]:
    """Users whose trimmed lower(name) equals ``lowered`` and pass allow rules."""
    conds = [User.role == "admin"]
    if effective_org_id is not None:
        conds.append(User.organization_id == effective_org_id)
    if staff_ids:
        conds.append(User.id.in_(staff_ids))
    return (
        db.query(User)
        .filter(
            User.name.isnot(None),
            func.lower(func.trim(User.name)) == lowered,
            or_(*conds),
        )
        .all()
    )


def resolve_mentioned_user_ids(
    db: Session,
    sender: User,
    channel_organization_id: Optional[int],
    content: str,
) -> List[int]:
    """
    Parse @**Name** in ``content`` and return sorted unique user IDs.

    ``channel_organization_id`` is ``None`` for announce channels; the sender's
    organization is then used as the school scope for non-admin targets.

    Raises:
        MentionResolutionError: unknown or ambiguous display names.
    """
    labels = parse_mention_display_names(content)
    if not labels:
        return []

    effective_org = channel_organization_id
    if effective_org is None:
        effective_org = sender.organization_id

    staff_ids = _staff_id_set()
    unknown: List[str] = []
    ambiguous: List[str] = []
    resolved_ids: List[int] = []

    for label in labels:
        lowered = label.strip().lower()
        if not lowered:
            continue
        matches = _users_matching_mention(
            db, lowered, effective_org, staff_ids,
        )
        if len(matches) == 0:
            unknown.append(label)
        elif len(matches) > 1:
            ambiguous.append(label)
        else:
            resolved_ids.append(matches[0].id)

    if unknown or ambiguous:
        raise MentionResolutionError(unknown, ambiguous)

    return sorted(set(resolved_ids))
