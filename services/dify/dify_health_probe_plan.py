"""
Build a deduplicated Dify failover heartbeat probe plan.

Platform monitoring walks every schema slot (1, 2, 3, …) and probes each unique
base URL once. Candidate app keys from every school on that host are kept so the
poller can retry on auth failure without treating a bad key as host-down.
Per-school failover still uses only the two servers that school configured.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import DefaultDict, Dict, List, Set, Tuple

from models.domain.auth import Organization
from services.dify.dify_server_schema import organization_dify_server_slots
from services.dify.dify_servers import org_server_credentials


def normalize_dify_probe_url(api_url: str) -> str:
    """Normalize a Dify base URL for host-level probe deduplication."""
    return (api_url or "").strip().rstrip("/")


@dataclass(frozen=True)
class DifyProbeTarget:
    """One Dify host to probe, with candidate app keys for the HTTP check."""

    api_url: str
    api_keys: Tuple[str, ...]

    @property
    def api_key(self) -> str:
        """First candidate key (compat for single-key call sites)."""
        return self.api_keys[0] if self.api_keys else ""


@dataclass(frozen=True)
class DifyProbeAssignment:
    """Maps a probe result back to one school's server slot."""

    org_id: int
    server: int
    target: DifyProbeTarget


def probe_target_key(target: DifyProbeTarget) -> str:
    """Stable dedupe key for a Dify host (base URL only)."""
    return normalize_dify_probe_url(target.api_url)


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
        """Number of HTTP host probes required this cycle."""
        return len(self.unique_targets)


def build_deduped_probe_plan(orgs: List[Organization]) -> DifyProbePlan:
    """
    Build a platform-wide heartbeat plan.

    Iterates every Organization schema slot (1, 2, 3, …) and every school that
    configures credentials on that slot. Each unique base URL is probed once;
    results fan out to every org/server assignment that shares that host.
    Candidate keys are ordered by org_id then server for stable selection.
    """
    grouped: DefaultDict[str, List[DifyProbeAssignment]] = defaultdict(list)
    keys_by_url: DefaultDict[str, List[str]] = defaultdict(list)
    seen_keys_by_url: Dict[str, Set[str]] = defaultdict(set)
    server_slot_count = 0
    monitored_slots: Set[int] = set()
    contributing_org_ids: Set[int] = set()

    ordered_orgs = sorted(orgs, key=lambda org: int(org.id))

    for server in organization_dify_server_slots():
        slot_used = False
        for org in ordered_orgs:
            creds = org_server_credentials(org, server)
            if creds is None:
                continue
            api_key, api_url = creds
            normalized_url = normalize_dify_probe_url(api_url)
            school_target = DifyProbeTarget(api_url=normalized_url, api_keys=(api_key,))
            grouped[normalized_url].append(DifyProbeAssignment(org_id=org.id, server=server, target=school_target))
            if api_key not in seen_keys_by_url[normalized_url]:
                seen_keys_by_url[normalized_url].add(api_key)
                keys_by_url[normalized_url].append(api_key)
            server_slot_count += 1
            slot_used = True
            contributing_org_ids.add(org.id)
        if slot_used:
            monitored_slots.add(server)

    unique_targets: List[DifyProbeTarget] = []
    assignments_by_target: List[Tuple[DifyProbeTarget, Tuple[DifyProbeAssignment, ...]]] = []
    for url in sorted(grouped.keys()):
        slot_assignments = grouped[url]
        target = DifyProbeTarget(api_url=url, api_keys=tuple(keys_by_url[url]))
        unique_targets.append(target)
        assignments_by_target.append((target, tuple(slot_assignments)))

    return DifyProbePlan(
        unique_targets=tuple(unique_targets),
        assignments_by_target=tuple(assignments_by_target),
        contributing_school_count=len(contributing_org_ids),
        server_slot_count=server_slot_count,
        monitored_schema_slots=tuple(sorted(monitored_slots)),
    )
