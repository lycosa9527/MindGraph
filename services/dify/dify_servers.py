"""
Pure helpers for per-organization Dify server credentials.

Server slots are discovered from the Organization ORM columns (see
``dify_server_schema``). ``dify_active_server`` selects the primary for live
MindMate chat; export and the heartbeat poller use every configured slot on
each org. These helpers are synchronous and side-effect free.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, cast

from models.domain.auth import Organization
from services.dify.dify_server_schema import (
    organization_dify_server_slots,
    server_slot_field_names,
)

# Failover auto-switch applies only when a school configures exactly this many servers.
FAILOVER_CONFIGURED_SERVER_COUNT = 2
MIN_FAILOVER_PROBE_SERVERS = FAILOVER_CONFIGURED_SERVER_COUNT


@dataclass(frozen=True)
class DifyServerCreds:
    """Resolved credentials for one Dify server of one organization."""

    server: int
    api_key: str
    api_url: str


def _field(org: Organization, name: str) -> str:
    """Stripped string value of an organization attribute (empty when unset)."""
    return (cast(Optional[str], getattr(org, name, None)) or "").strip()


def org_server_credentials(org: Organization, server: int) -> Optional[tuple[str, str]]:
    """Return ``(api_key, api_url)`` for *server* when both are set, else None."""
    fields = server_slot_field_names(server)
    if fields is None:
        return None
    url_field, key_field = fields
    api_url = _field(org, url_field)
    api_key = _field(org, key_field)
    if api_url and api_key:
        return api_key, api_url
    return None


def primary_server_no(org: Organization) -> int:
    """Return the configured primary server number (defaults to the first slot)."""
    slots = organization_dify_server_slots()
    default = slots[0] if slots else 1
    raw = getattr(org, "dify_active_server", default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value in slots else default


def failover_partner_server(org: Organization) -> Optional[int]:
    """
    The other server in this org's configured failover pair.

    Schools pick any two slots (e.g. 1+2, 2+3, or 1+3); the partner is whichever
    configured slot is not the primary. Requires exactly two configured servers.
    """
    primary = primary_server_no(org)
    slots = sorted(entry.server for entry in configured_dify_servers(org))
    if len(slots) != FAILOVER_CONFIGURED_SERVER_COUNT:
        return None
    if primary not in slots:
        return slots[0]
    others = [slot for slot in slots if slot != primary]
    return others[0] if others else None


def standby_server_no(server: int) -> int:
    """Legacy two-slot helper (server 1 <-> 2 only). Prefer ``failover_partner_server``."""
    return 2 if server == 1 else 1


def failover_enabled(org: Organization) -> bool:
    """True when active/standby auto-switch is enabled for this organization."""
    return bool(getattr(org, "dify_failover_enabled", True))


def configured_dify_servers(org: Organization) -> List[DifyServerCreds]:
    """Every schema slot on this org that has both URL and key configured."""
    out: List[DifyServerCreds] = []
    for server in organization_dify_server_slots():
        creds = org_server_credentials(org, server)
        if creds is not None:
            api_key, api_url = creds
            out.append(DifyServerCreds(server=server, api_key=api_key, api_url=api_url))
    return out


def org_eligible_for_failover_probing(org: Organization) -> bool:
    """True when background health checks should cover this school's Dify servers."""
    return failover_enabled(org) and failover_partner_server(org) is not None
