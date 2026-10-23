"""
Resolve AsyncDifyClient for MindMate from organization override or global env.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
from typing import NamedTuple, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clients.dify import AsyncDifyClient
from models.domain.auth import Organization
from services.dify.dify_failover_routing import choose_failover_route, is_health_fresh
from services.dify.dify_global_servers import (
    effective_configured_dify_servers,
    effective_server_credentials,
    global_dify_main_url,
    global_dify_servers,
    global_dify_slot_credentials,
)
from services.dify.dify_health_logging import LOG_PREFIX, org_label, server_label
from services.dify.dify_servers import (
    DifyServerCreds,
    configured_dify_servers,
    failover_enabled,
    partner_for_configured_slots,
    primary_server_no,
)
from services.redis.cache.redis_dify_server_health_cache import get_url_health
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)


class MindmateDifyNotConfiguredError(Exception):
    """Raised when neither org override nor global Dify credentials are available."""


class MindmateDifyStream(NamedTuple):
    """Live chat target: client, backup notice, id to send, and the server used."""

    client: AsyncDifyClient
    notify_backup: bool
    upstream_conversation_id: Optional[str]
    server: Optional[int]


def conversation_owner_server(
    conversation_id: Optional[str],
    conversation_server: Optional[int],
) -> Optional[int]:
    """
    Server that already owns this conversation.

    A new chat has no owner. An id without a server number was opened on
    主服务器. Bool is rejected because it is an ``int`` subclass.
    """
    if not (conversation_id or "").strip():
        return None
    if isinstance(conversation_server, bool) or not isinstance(conversation_server, int):
        return 1
    if conversation_server >= 1:
        return conversation_server
    return 1


def upstream_conversation_id(
    conversation_id: Optional[str],
    owner: Optional[int],
    chosen: Optional[int],
) -> Optional[str]:
    """Drop the id when this turn is not on the server that owns the thread."""
    if not (conversation_id or "").strip():
        return None
    if owner is not None and chosen is not None and owner != chosen:
        return None
    return conversation_id


def _global_dify_credentials() -> tuple[str, str, int]:
    """Dify main credentials (school 主服务器) plus the shared timeout."""
    timeout = int(os.getenv("DIFY_TIMEOUT", "300"))
    creds = global_dify_slot_credentials(1)
    if creds is None:
        return "", global_dify_main_url(), timeout
    api_key, api_url = creds
    return api_key, api_url, timeout


def global_mindmate_dify_credentials() -> tuple[str, str]:
    """Return global MindMate Dify API key and base URL from environment."""
    api_key, api_url, _timeout = _global_dify_credentials()
    return api_key, api_url


async def _load_org(db: AsyncSession, organization_id: int) -> Optional[Organization]:
    """Load an organization row or None."""
    result = await db.execute(select(Organization).where(Organization.id == organization_id))
    return result.scalar_one_or_none()


def using_backup_after_main_outage(org: Organization, server_no: Optional[int]) -> bool:
    """
    True when live chat left 主服务器 (slot 1) for 备用服务器 (slot 2).

    A school that set 优先使用 to 备用服务器 is already on that slot, so this
    stays false. A blank 主服务器 that simply falls through to slot 2 is also
    false: that is not an outage.
    """
    if server_no != 2 or primary_server_no(org) != 1 or not failover_enabled(org):
        return False
    configured = {entry.server for entry in effective_configured_dify_servers(org)}
    return 1 in configured and 2 in configured


async def select_active_dify_server(org: Organization) -> Optional[int]:
    """
    Choose the live Dify server for an org with active/standby failover.

    Prefers the configured primary; when failover is enabled and the primary is
    considered down (per the health cache) while the partner slot is usable,
    returns the partner. The primary is preferred again as soon as it recovers.

    The partner follows the school's effective pair. A blank 主服务器 or
    备用服务器 uses Dify main or Dify backup from the environment when backup is set.
    """
    primary = primary_server_no(org)
    servers = effective_configured_dify_servers(org)
    by_server = {entry.server: entry for entry in servers}
    partner = partner_for_configured_slots(primary, list(by_server))
    primary_creds = by_server.get(primary)
    partner_creds = by_server.get(partner) if partner is not None else None

    if primary_creds is None:
        if partner_creds is not None:
            return partner
        return servers[0].server if servers else None
    if not failover_enabled(org) or partner is None or partner_creds is None:
        return primary

    primary_health = await get_url_health(primary_creds.api_url)
    partner_health = await get_url_health(partner_creds.api_url)
    route = choose_failover_route(primary, partner, primary_health, partner_health)
    if route == partner and route != primary:
        if primary_health is not None and not is_health_fresh(primary_health):
            logger.warning(
                "%s %s: MindMate routed to %s; %s health data is stale.",
                LOG_PREFIX,
                org_label(org),
                server_label(partner, "standby"),
                server_label(primary, "primary"),
            )
        else:
            logger.debug(
                "%s %s: MindMate request routed to %s because %s is offline.",
                LOG_PREFIX,
                org_label(org),
                server_label(partner, "standby"),
                server_label(primary, "primary"),
            )
        return partner
    return primary


async def _conversation_server_usable(org: Organization, server: int) -> bool:
    """True when this conversation's server is not known to be down."""
    creds = effective_server_credentials(org, server)
    if creds is None:
        return False
    health = await get_url_health(creds[1])
    if health is None:
        return True
    if not is_health_fresh(health):
        return False
    return not health.considered_down


async def select_stream_dify_server(
    org: Organization,
    owner: Optional[int],
) -> tuple[Optional[int], bool]:
    """
    Pick the server for one chat turn and whether to show the backup notice.

    The conversation stays on its own server until that server is considered
    down. Otherwise the live failover route is used. The notice is set only
    when that route left 主服务器 for 备用服务器 and this thread does not
    already live there.
    """
    active = await select_active_dify_server(org)
    chosen = active
    if owner is not None and owner != active and await _conversation_server_usable(org, owner):
        chosen = owner
    notify = using_backup_after_main_outage(org, chosen) and chosen != owner
    return chosen, notify


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
    Every effective Dify server for an org (used by export to query both).

    School overrides win. A blank 主服务器 or 备用服务器 uses Dify main or
    Dify backup when the backup pair is set. Otherwise falls back to Dify main.
    """
    if organization_id is not None:
        async with system_rls_session() as db:
            org = await _load_org(db, organization_id)
        if org is not None:
            effective = effective_configured_dify_servers(org)
            if effective:
                return effective
    return global_dify_servers()


async def _resolve_mindmate_dify(
    db: AsyncSession,
    organization_id: Optional[int],
    *,
    conversation_id: Optional[str] = None,
    conversation_server: Optional[int] = None,
) -> MindmateDifyStream:
    """
    Build the MindMate Dify client for one chat turn.

    ``notify_backup`` is true only when failover moved this turn onto
    备用服务器 and the open thread does not already live there.
    """
    api_key = ""
    api_url = ""
    timeout = int(os.getenv("DIFY_TIMEOUT", "300"))
    org_timeout_set = False
    notify_backup = False
    server_no: Optional[int] = None
    owner = conversation_owner_server(conversation_id, conversation_server)

    if organization_id is not None:
        org = await _load_org(db, organization_id)
        if org is not None:
            org_timeout = getattr(org, "dify_timeout_seconds", None)
            if org_timeout is not None:
                timeout = int(org_timeout)
                org_timeout_set = True
            server_no, notify_backup = await select_stream_dify_server(org, owner)
            if server_no is not None:
                creds = effective_server_credentials(org, server_no)
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

    client = AsyncDifyClient(api_key=api_key, api_url=api_url, timeout=timeout)
    return MindmateDifyStream(
        client,
        notify_backup,
        upstream_conversation_id(conversation_id, owner, server_no),
        server_no,
    )


async def resolve_mindmate_dify_client(
    db: AsyncSession,
    organization_id: Optional[int],
) -> AsyncDifyClient:
    """
    Build Dify client for MindMate: per-org active server (with failover) when
    configured, otherwise global ``DIFY_API_*`` environment variables.
    """
    target = await _resolve_mindmate_dify(db, organization_id)
    return target.client


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


async def resolve_mindmate_dify_stream_short_lived(
    organization_id: Optional[int],
    *,
    detail: str,
    conversation_id: Optional[str] = None,
    conversation_server: Optional[int] = None,
) -> MindmateDifyStream:
    """
    Resolve the stream target for one chat turn.

    ``notify_backup`` is true only for a failover off 主服务器 onto 备用服务器
    when the open thread does not already live on 备用服务器.
    """
    async with system_rls_session() as db:
        try:
            return await _resolve_mindmate_dify(
                db,
                organization_id,
                conversation_id=conversation_id,
                conversation_server=conversation_server,
            )
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
    target = await resolve_mindmate_dify_stream_short_lived(
        organization_id,
        detail=detail,
    )
    return target.client
