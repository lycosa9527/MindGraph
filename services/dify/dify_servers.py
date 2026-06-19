"""
Pure helpers for per-organization dual Dify server credentials.

Server 1 reuses the legacy ``dify_api_base_url``/``dify_api_key`` columns;
Server 2 uses ``dify_api_base_url_2``/``dify_api_key_2``. ``dify_active_server``
selects the primary for live MindMate chat; the export module queries every
configured server. These helpers are synchronous and side-effect free so they
can be reused by the resolver, the heartbeat poller and the export collector.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, cast

from models.domain.auth import Organization

VALID_SERVERS: tuple[int, int] = (1, 2)


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
    """
    Return ``(api_key, api_url)`` for *server* (1 or 2) when both are set, else None.
    """
    if server == 1:
        api_url = _field(org, "dify_api_base_url")
        api_key = _field(org, "dify_api_key")
    elif server == 2:
        api_url = _field(org, "dify_api_base_url_2")
        api_key = _field(org, "dify_api_key_2")
    else:
        return None
    if api_url and api_key:
        return api_key, api_url
    return None


def primary_server_no(org: Organization) -> int:
    """Return the configured primary server number (defaults to 1)."""
    raw = getattr(org, "dify_active_server", 1)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 1
    return value if value in VALID_SERVERS else 1


def standby_server_no(server: int) -> int:
    """Return the other server number for a given primary."""
    return 2 if server == 1 else 1


def failover_enabled(org: Organization) -> bool:
    """True when active/standby auto-switch is enabled for this organization."""
    return bool(getattr(org, "dify_failover_enabled", True))


def configured_dify_servers(org: Organization) -> List[DifyServerCreds]:
    """All fully-configured servers for this org, ordered by server number."""
    out: List[DifyServerCreds] = []
    for server in VALID_SERVERS:
        creds = org_server_credentials(org, server)
        if creds is not None:
            api_key, api_url = creds
            out.append(DifyServerCreds(server=server, api_key=api_key, api_url=api_url))
    return out
