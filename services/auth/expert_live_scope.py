"""
Which schools should list a bound expert right now.

Binding rows are the source of truth. Live presence and open rooms keep a
copy in memory and Redis, so a save has to move that copy.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations


def parse_bound_org_label(raw: str) -> list[int]:
    """Split a comma-separated org id label."""
    org_ids: list[int] = []
    seen: set[int] = set()
    for piece in raw.split(","):
        token = piece.strip()
        if not token.isdigit():
            continue
        org_id = int(token)
        if org_id <= 0 or org_id in seen:
            continue
        seen.add(org_id)
        org_ids.append(org_id)
    return org_ids


def session_registry_org_ids(host_org_id: int | None, bound_org_ids: list[int]) -> list[int]:
    """Schools that should list one organization-visibility room.

    An empty result means the room has no school. Callers must not put that
    room on the global registry when the host is an expert.
    """
    ordered: list[int] = []
    seen: set[int] = set()
    if host_org_id is not None and int(host_org_id) > 0:
        host = int(host_org_id)
        ordered.append(host)
        seen.add(host)
    for raw in bound_org_ids:
        org_id = int(raw)
        if org_id <= 0 or org_id in seen:
            continue
        seen.add(org_id)
        ordered.append(org_id)
    return ordered


def bound_org_label(host_org_id: int | None, bound_org_ids: list[int]) -> str:
    """Redis label of bound schools, without repeating the host school."""
    host = int(host_org_id) if host_org_id is not None else None
    extras = [org_id for org_id in session_registry_org_ids(None, bound_org_ids) if org_id != host]
    return ",".join(str(org_id) for org_id in extras)
