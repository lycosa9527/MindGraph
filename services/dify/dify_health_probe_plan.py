"""
Build a deduplicated Dify failover heartbeat probe plan.

Platform monitoring walks every schema slot (1, 2, 3, …) and probes each unique
URL/key used by any school on that slot. Per-school failover still uses only the
two servers that school configured.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import DefaultDict, List, Set, Tuple

from models.domain.auth import Organization
from services.dify.dify_server_schema import organization_dify_server_slots
from services.dify.dify_servers import org_server_credentials


@dataclass(frozen=True)
class DifyProbeTarget:
    """One Dify app API origin to probe (URL + app key)."""

    api_url: str
    api_key: str


@dataclass(frozen=True)
class DifyProbeAssignment:
    """Maps a probe result back to one school's server slot."""

    org_id: int
    server: int
    target: DifyProbeTarget


def probe_target_key(target: DifyProbeTarget) -> Tuple[str, str]:
    """Stable dedupe key for identical endpoints."""
    return (target.api_url, target.api_key)


@dataclass(frozen=True)
class DifyProbePlan:
    """Deduped probe targets and the school/server slots that consume each result."""

    unique_targets: Tuple[DifyProbeTarget, ...]
    assignments_by_target: Tuple[Tuple[DifyProbeTarget, Tuple[DifyProbeAssignment, ...]], ...]
    contributing_school_count: int
    server_slot_count: int
    monitored_schema_slots: Tuple[int, ...]

    @property
    def unique_endpoint_count(self) -> int:
        """Number of HTTP probes required this cycle."""
        return len(self.unique_targets)


def build_deduped_probe_plan(orgs: List[Organization]) -> DifyProbePlan:
    """
    Build a platform-wide heartbeat plan.

    Iterates every Organization schema slot (1, 2, 3, …) and every school that
    configures credentials on that slot. Each unique URL/key is probed once; results
    fan out to every org/server assignment that shares the endpoint.
    """
    grouped: DefaultDict[Tuple[str, str], List[DifyProbeAssignment]] = defaultdict(list)
    server_slot_count = 0
    monitored_slots: Set[int] = set()
    contributing_org_ids: Set[int] = set()

    for server in organization_dify_server_slots():
        slot_used = False
        for org in orgs:
            creds = org_server_credentials(org, server)
            if creds is None:
                continue
            api_key, api_url = creds
            target = DifyProbeTarget(api_url=api_url, api_key=api_key)
            grouped[probe_target_key(target)].append(DifyProbeAssignment(org_id=org.id, server=server, target=target))
            server_slot_count += 1
            slot_used = True
            contributing_org_ids.add(org.id)
        if slot_used:
            monitored_slots.add(server)

    unique_targets: List[DifyProbeTarget] = []
    assignments_by_target: List[Tuple[DifyProbeTarget, Tuple[DifyProbeAssignment, ...]]] = []
    for key, slot_assignments in grouped.items():
        target = DifyProbeTarget(api_url=key[0], api_key=key[1])
        unique_targets.append(target)
        assignments_by_target.append((target, tuple(slot_assignments)))

    return DifyProbePlan(
        unique_targets=tuple(unique_targets),
        assignments_by_target=tuple(assignments_by_target),
        contributing_school_count=len(contributing_org_ids),
        server_slot_count=server_slot_count,
        monitored_schema_slots=tuple(sorted(monitored_slots)),
    )
