"""
Resolve AsyncDifyClient for MindMate from organization override or global env.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clients.dify import AsyncDifyClient
from models.domain.auth import Organization
from services.dify.dify_servers import (
    DifyServerCreds,
    configured_dify_servers,
    failover_enabled,
    org_server_credentials,
    primary_server_no,
    standby_server_no,
)
from services.redis.cache.redis_dify_server_health_cache import get_server_health
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)


class MindmateDifyNotConfiguredError(Exception):
    """Raised when neither org override nor global Dify credentials are available."""


def _global_dify_credentials() -> tuple[str, str, int]:
    """Global dify credentials."""
    api_key = (os.getenv("DIFY_API_KEY") or "").strip()
    api_url = (os.getenv("DIFY_API_URL") or "https://api.dify.ai/v1").strip()
    timeout = int(os.getenv("DIFY_TIMEOUT", "300"))
    return api_key, api_url, timeout


def global_mindmate_dify_credentials() -> tuple[str, str]:
    """Return global MindMate Dify API key and base URL from environment."""
    api_key, api_url, _timeout = _global_dify_credentials()
    return api_key, api_url


async def _load_org(db: AsyncSession, organization_id: int) -> Optional[Organization]:
    """Load an organization row or None."""
    result = await db.execute(select(Organization).where(Organization.id == organization_id))
    return result.scalar_one_or_none()


async def select_active_dify_server(org: Organization) -> Optional[int]:
    """
    Choose the live Dify server for an org with active/standby failover.

    Prefers the configured primary; when failover is enabled and the primary is
    considered down (per the health cache) while the standby is usable, returns
    the standby. The primary is preferred again as soon as it recovers.
    """
    primary = primary_server_no(org)
    standby = standby_server_no(primary)
    primary_creds = org_server_credentials(org, primary)
    standby_creds = org_server_credentials(org, standby)

    if primary_creds is None:
        return standby if standby_creds is not None else None
    if not failover_enabled(org) or standby_creds is None:
        return primary

    primary_health = await get_server_health(org.id, primary)
    if primary_health is None or not primary_health.considered_down:
        return primary

    standby_health = await get_server_health(org.id, standby)
    if standby_health is None or not standby_health.considered_down:
        logger.info(
            "[Dify] Org %s failing over from server %s to server %s (primary unhealthy)",
            org.id,
            primary,
            standby,
        )
        return standby
    return primary


async def resolve_org_dify_servers_strict(organization_id: int) -> list[DifyServerCreds]:
    """
    Org-only Dify servers with no global fallback.

    Returns an empty list when the organization row is missing or has no
    per-server credentials configured.
    """
    async with system_rls_session() as db:
        org = await _load_org(db, organization_id)
    if org is None:
        return []
    return configured_dify_servers(org)


async def resolve_all_dify_servers(organization_id: Optional[int]) -> list[DifyServerCreds]:
    """
    Every configured Dify server for an org (used by export to query both).

    Falls back to the global ``DIFY_API_*`` server (numbered 1) when the org has
    no per-server credentials configured.
    """
    if organization_id is not None:
        strict = await resolve_org_dify_servers_strict(organization_id)
        if strict:
            return strict
    global_key, global_url, _timeout = _global_dify_credentials()
    if global_key and global_url:
        return [DifyServerCreds(server=1, api_key=global_key, api_url=global_url)]
    return []


async def resolve_mindmate_dify_client(
    db: AsyncSession,
    organization_id: Optional[int],
) -> AsyncDifyClient:
    """
    Build Dify client for MindMate: per-org active server (with failover) when
    configured, otherwise global ``DIFY_API_*`` environment variables.
    """
    api_key = ""
    api_url = ""
    timeout = int(os.getenv("DIFY_TIMEOUT", "300"))
    org_timeout_set = False

    if organization_id is not None:
        org = await _load_org(db, organization_id)
        if org is not None:
            org_timeout = getattr(org, "dify_timeout_seconds", None)
            if org_timeout is not None:
                timeout = int(org_timeout)
                org_timeout_set = True
            server_no = await select_active_dify_server(org)
            if server_no is not None:
                creds = org_server_credentials(org, server_no)
                if creds is not None:
                    api_key, api_url = creds

    if not api_key:
        global_key, global_url, global_timeout = _global_dify_credentials()
        api_key = global_key
        api_url = global_url
        if not org_timeout_set:
            timeout = global_timeout

    if not api_key:
        raise MindmateDifyNotConfiguredError()

    return AsyncDifyClient(api_key=api_key, api_url=api_url, timeout=timeout)


async def resolve_mindmate_dify_client_or_http(
    db: AsyncSession,
    organization_id: Optional[int],
    *,
    detail: str,
) -> AsyncDifyClient:
    """Like ``resolve_mindmate_dify_client`` but raises HTTP 500 with *detail* if unconfigured."""
    try:
        return await resolve_mindmate_dify_client(db, organization_id)
    except MindmateDifyNotConfiguredError as exc:
        raise HTTPException(status_code=500, detail=detail) from exc


async def resolve_mindmate_dify_client_short_lived(
    organization_id: Optional[int],
    *,
    detail: str,
) -> AsyncDifyClient:
    """
    Resolve MindMate Dify client using a short-lived DB session.

    Use for routes that await slow upstream Dify HTTP after credential lookup, so the
    request-scoped session is not held open past idle_in_transaction_session_timeout.
    """
    async with system_rls_session() as db:
        return await resolve_mindmate_dify_client_or_http(
            db,
            organization_id,
            detail=detail,
        )
