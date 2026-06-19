"""
Export Dify endpoint descriptors (org MindMate servers + MindBot apps).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from models.domain.auth import Organization
from services.dify.dify_servers import DifyServerCreds
from services.dify.org_mindmate_client import resolve_all_dify_servers, resolve_org_dify_servers_strict
from services.mindbot.dify.credential_resolution import (
    MindbotDifyEndpoint,
    distinct_mindbot_endpoints_for_org,
    staff_id_from_mindbot_dify_user,
)

__all__ = [
    "ExportDifyEndpoint",
    "endpoints_for_target",
    "endpoint_lookup_key",
    "resolve_endpoint_for_message_fetch",
]


@dataclass(frozen=True)
class ExportDifyEndpoint:
    """One Dify Service API origin used during export collection."""

    organization_id: int
    source: str
    server: int
    mindbot_config_id: Optional[int]
    api_key: str
    api_url: str

    def lookup_key(self) -> tuple[int, str, int, Optional[int]]:
        """Stable cache key within one export request."""
        return (self.organization_id, self.source, self.server, self.mindbot_config_id)


def endpoint_lookup_key(
    organization_id: int,
    source: str,
    server: int,
    mindbot_config_id: Optional[int],
) -> tuple[int, str, int, Optional[int]]:
    """Build lookup key matching ``ExportDifyEndpoint.lookup_key``."""
    return (organization_id, source, server, mindbot_config_id)


def _org_creds_to_endpoints(org_id: int, creds: List[DifyServerCreds]) -> List[ExportDifyEndpoint]:
    return [
        ExportDifyEndpoint(
            organization_id=org_id,
            source="org_server",
            server=creds_item.server,
            mindbot_config_id=None,
            api_key=creds_item.api_key,
            api_url=creds_item.api_url,
        )
        for creds_item in creds
    ]


def _mindbot_to_endpoints(org_id: int, items: List[MindbotDifyEndpoint]) -> List[ExportDifyEndpoint]:
    out: List[ExportDifyEndpoint] = []
    for index, item in enumerate(items, start=1):
        out.append(
            ExportDifyEndpoint(
                organization_id=org_id,
                source="mindbot_config",
                server=index,
                mindbot_config_id=item.mindbot_config_id,
                api_key=item.api_key,
                api_url=item.api_url,
            )
        )
    return out


async def endpoints_for_target(
    org: Organization,
    *,
    channel: str,
    dify_user: str,
    db,
    strict_org: bool = False,
) -> List[ExportDifyEndpoint]:
    """Resolve Dify endpoints for one export target identity."""
    org_id = int(org.id)
    if channel == "web":
        if strict_org:
            creds = await resolve_org_dify_servers_strict(org_id)
        else:
            creds = await resolve_all_dify_servers(org_id)
        return _org_creds_to_endpoints(org_id, creds)

    staff_id = staff_id_from_mindbot_dify_user(dify_user)
    mindbot_items = await distinct_mindbot_endpoints_for_org(db, org, staff_id=staff_id)
    if mindbot_items:
        return _mindbot_to_endpoints(org_id, mindbot_items)

    if strict_org:
        creds = await resolve_org_dify_servers_strict(org_id)
    else:
        creds = await resolve_all_dify_servers(org_id)
    return _org_creds_to_endpoints(org_id, creds)


async def resolve_endpoint_for_message_fetch(
    db,
    org: Organization,
    *,
    channel: str,
    server: int,
    mindbot_config_id: Optional[int],
    dify_user: str,
    strict_org: bool = True,
) -> Optional[ExportDifyEndpoint]:
    """Pick the endpoint used to fetch messages for one conversation row."""
    endpoints = await endpoints_for_target(
        org,
        channel=channel,
        dify_user=dify_user,
        db=db,
        strict_org=strict_org,
    )
    if channel == "mindbot" and mindbot_config_id is not None:
        for endpoint in endpoints:
            if endpoint.mindbot_config_id == int(mindbot_config_id):
                return endpoint
    for endpoint in endpoints:
        if endpoint.server == int(server):
            return endpoint
    return endpoints[0] if endpoints else None
