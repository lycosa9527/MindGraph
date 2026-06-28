"""
Unified MindMate conversation list (web + bound DingTalk MindBot identities).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple, Type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clients.dify import AsyncDifyClient
from clients.dify_exceptions import DifyAPIError, DifyConversationNotFoundError
from models.domain.auth import Organization, User
from services.dify.export.endpoints import (
    ExportDifyEndpoint,
    endpoints_for_target,
    resolve_endpoint_for_message_fetch,
)
from services.dify.export.target_resolution import build_user_dify_targets
from services.dify.export.transcript import ExportConversationSummary
from services.dify.export.types import UserTarget
from services.dify.export.usage_supplement import supplement_mindbot_summaries_from_usage
from services.dify.org_mindmate_client import resolve_mindmate_dify_client
from utils.db.session_open import system_rls_session
from utils.dify_mindmate_user_id import mindmate_dify_user_id

logger = logging.getLogger(__name__)

DEFAULT_LIST_TIMEOUT = int(os.getenv("DIFY_TIMEOUT", "300"))

dify_client_errors: Tuple[Type[Exception], ...] = (
    DifyAPIError,
    ConnectionError,
    TimeoutError,
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    KeyError,
)

try:
    from aiohttp import ClientError as _aiohttp_client_error
except ImportError:
    pass
else:
    dify_client_errors = dify_client_errors + (_aiohttp_client_error,)


@dataclass(frozen=True)
class UnifiedConversation:
    """One conversation row in the merged web + MindBot history list."""

    id: str
    name: str
    created_at: int
    updated_at: int
    channel: str
    dify_user: str
    server: int = 1
    mindbot_config_id: Optional[int] = None


async def _load_org(org_id: int) -> Optional[Organization]:
    async with system_rls_session() as db:
        return (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()


def _client_for_endpoint(endpoint: ExportDifyEndpoint) -> AsyncDifyClient:
    return AsyncDifyClient(
        api_key=endpoint.api_key,
        api_url=endpoint.api_url,
        timeout=DEFAULT_LIST_TIMEOUT,
    )


async def _endpoints_for_target(
    db: AsyncSession,
    target: UserTarget,
    org_by_id: dict[int, Organization],
) -> List[ExportDifyEndpoint]:
    org_id = int(target.organization_id)
    if org_id > 0:
        org = org_by_id.get(org_id)
        if org is None:
            org = await _load_org(org_id)
            if org is not None:
                org_by_id[org_id] = org
        if org is not None:
            endpoint_items = await endpoints_for_target(
                org,
                channel=target.channel,
                dify_user=target.dify_user,
                db=db,
                strict_org=False,
            )
            if endpoint_items:
                return endpoint_items

    client = await resolve_mindmate_dify_client(db, org_id if org_id > 0 else None)
    return [
        ExportDifyEndpoint(
            organization_id=max(org_id, 0),
            source="org_server",
            server=1,
            mindbot_config_id=None,
            api_key=client.api_key,
            api_url=client.api_url,
        )
    ]


def _summary_from_dify_row(
    item: dict,
    target: UserTarget,
    endpoint: ExportDifyEndpoint,
) -> Optional[ExportConversationSummary]:
    conv_id = str(item.get("id") or "").strip()
    if not conv_id:
        return None
    created = int(item.get("created_at") or 0)
    updated = int(item.get("updated_at") or created)
    return ExportConversationSummary(
        conversation_id=conv_id,
        name=str(item.get("name") or ""),
        server=int(endpoint.server),
        organization_id=int(target.organization_id),
        dify_user=target.dify_user,
        user_id=target.user_id,
        user_label=target.label,
        channel=target.channel,
        mindbot_config_id=endpoint.mindbot_config_id,
        endpoint_source=endpoint.source,
        created_at=created,
        updated_at=updated,
    )


def _summary_dedupe_key(summary: ExportConversationSummary) -> str:
    return f"{summary.server}:{summary.dify_user}:{summary.conversation_id}"


def _summary_to_unified(summary: ExportConversationSummary) -> UnifiedConversation:
    return UnifiedConversation(
        id=summary.conversation_id,
        name=summary.name,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
        channel=summary.channel,
        dify_user=summary.dify_user,
        server=int(summary.server),
        mindbot_config_id=summary.mindbot_config_id,
    )


async def _fetch_target_summaries_page(
    db: AsyncSession,
    target: UserTarget,
    org_by_id: dict[int, Organization],
    *,
    limit: int,
) -> List[ExportConversationSummary]:
    """Fetch one page of conversations for one identity across all Dify endpoints."""
    endpoints = await _endpoints_for_target(db, target, org_by_id)
    if not endpoints:
        return []

    merged: dict[str, ExportConversationSummary] = {}
    for endpoint in endpoints:
        try:
            client = _client_for_endpoint(endpoint)
            result = await client.get_conversations(
                user_id=target.dify_user,
                limit=limit,
                sort_by="-updated_at",
            )
        except dify_client_errors as exc:
            logger.warning(
                "[UnifiedConversations] list failed user=%s channel=%s server=%s: %s",
                target.dify_user,
                target.channel,
                endpoint.server,
                exc,
            )
            continue

        for item in result.get("data") or []:
            if not isinstance(item, dict):
                continue
            summary = _summary_from_dify_row(item, target, endpoint)
            if summary is None:
                continue
            key = _summary_dedupe_key(summary)
            existing = merged.get(key)
            if existing is None or summary.updated_at >= existing.updated_at:
                merged[key] = summary

    return list(merged.values())


async def list_unified_conversations(
    db: AsyncSession,
    user: User,
    *,
    limit: int = 20,
    last_id: Optional[str] = None,
) -> Tuple[List[UnifiedConversation], bool]:
    """
    List conversations across web MindMate and bound MindBot Dify user keys.

    Fetches up to ``limit`` rows per identity and Dify endpoint, merges by
    ``updated_at``, supplements MindBot threads from usage telemetry, and
    returns the newest ``limit`` rows.
    """
    targets = await build_user_dify_targets(db, user)
    if not targets:
        return [], False

    if len(targets) == 1 and last_id:
        target = targets[0]
        org_by_id: dict[int, Organization] = {}
        org_id = int(target.organization_id)
        if org_id > 0:
            org = await _load_org(org_id)
            if org is not None:
                org_by_id[org_id] = org
        endpoints = await _endpoints_for_target(db, target, org_by_id)
        if len(endpoints) == 1:
            client = _client_for_endpoint(endpoints[0])
            result = await client.get_conversations(
                user_id=target.dify_user,
                last_id=last_id,
                limit=limit,
                sort_by="-updated_at",
            )
            rows = [
                _summary_to_unified(summary)
                for item in (result.get("data") or [])
                if isinstance(item, dict)
                for summary in [_summary_from_dify_row(item, target, endpoints[0])]
                if summary is not None
            ]
            return rows, bool(result.get("has_more", False))

    page_size = max(1, min(limit, 100))
    org_by_id = {}
    for org_id in {int(target.organization_id) for target in targets if int(target.organization_id) > 0}:
        org = await _load_org(org_id)
        if org is not None:
            org_by_id[org_id] = org

    flat: List[ExportConversationSummary] = []
    any_has_more = False
    for target in targets:
        endpoint_summaries = await _fetch_target_summaries_page(
            db,
            target,
            org_by_id,
            limit=page_size,
        )
        flat.extend(endpoint_summaries)
        if len(endpoint_summaries) >= page_size:
            any_has_more = True

    supplemented, supplement_warnings = await supplement_mindbot_summaries_from_usage(
        db,
        targets,
        flat,
    )
    for warning in supplement_warnings:
        logger.info("[UnifiedConversations] %s user=%s", warning, getattr(user, "id", "?"))

    ordered = sorted(supplemented, key=lambda row: row.updated_at, reverse=True)
    page = ordered[:page_size]
    has_more = any_has_more or len(ordered) > page_size
    mindbot_count = sum(1 for row in page if row.channel == "mindbot")
    logger.info(
        "[UnifiedConversations] listed user=%s targets=%d rows=%d mindbot=%d",
        getattr(user, "id", "?"),
        len(targets),
        len(page),
        mindbot_count,
    )
    return [_summary_to_unified(row) for row in page], has_more


def _ordered_dify_targets(targets: List[UserTarget]) -> List[UserTarget]:
    """Probe web identities before MindBot keys (common case, stable ordering)."""
    return sorted(targets, key=lambda target: (0 if target.channel == "web" else 1, target.dify_user))


async def _resolve_endpoint_for_conversation(
    db: AsyncSession,
    target: UserTarget,
    conversation_id: str,
    dify_user: str,
    *,
    server_hint: Optional[int] = None,
    mindbot_config_id_hint: Optional[int] = None,
) -> Optional[ExportDifyEndpoint]:
    org_id = int(target.organization_id)
    if org_id <= 0:
        return None
    org = await _load_org(org_id)
    if org is None:
        return None
    if server_hint is not None or mindbot_config_id_hint is not None:
        endpoint = await resolve_endpoint_for_message_fetch(
            db,
            org,
            channel=target.channel,
            server=int(server_hint or 1),
            mindbot_config_id=mindbot_config_id_hint,
            dify_user=dify_user,
            strict_org=False,
        )
        if endpoint is not None:
            return endpoint
    org_by_id = {org_id: org}
    for endpoint in await _endpoints_for_target(db, target, org_by_id):
        try:
            client = _client_for_endpoint(endpoint)
            await client.get_messages(
                conversation_id=conversation_id,
                user_id=dify_user,
                limit=1,
            )
            return endpoint
        except dify_client_errors:
            continue
    return None


async def resolve_dify_user_for_conversation(
    db: AsyncSession,
    user: User,
    conversation_id: str,
    *,
    dify_user_hint: Optional[str] = None,
    server_hint: Optional[int] = None,
    mindbot_config_id_hint: Optional[int] = None,
) -> str:
    """Pick the Dify ``user`` string that owns ``conversation_id``."""
    targets = await build_user_dify_targets(db, user)
    if not targets:
        raise DifyConversationNotFoundError()

    if dify_user_hint:
        hint = dify_user_hint.strip()
        if hint:
            hinted = next((target for target in targets if target.dify_user == hint), None)
            if hinted is not None:
                endpoint = await _resolve_endpoint_for_conversation(
                    db,
                    hinted,
                    conversation_id,
                    hint,
                    server_hint=server_hint,
                    mindbot_config_id_hint=mindbot_config_id_hint,
                )
                if endpoint is not None:
                    return hint

    for target in _ordered_dify_targets(targets):
        endpoint = await _resolve_endpoint_for_conversation(
            db,
            target,
            conversation_id,
            target.dify_user,
            server_hint=server_hint if target.dify_user == (dify_user_hint or "").strip() else None,
            mindbot_config_id_hint=(
                mindbot_config_id_hint if target.dify_user == (dify_user_hint or "").strip() else None
            ),
        )
        if endpoint is not None:
            return target.dify_user

    raise DifyConversationNotFoundError(f"Conversation {conversation_id} not found for any bound Dify identity")


async def resolve_client_and_dify_user(
    db: AsyncSession,
    user: User,
    conversation_id: str,
    *,
    dify_user_hint: Optional[str] = None,
    server_hint: Optional[int] = None,
    mindbot_config_id_hint: Optional[int] = None,
) -> Tuple[AsyncDifyClient, str]:
    """Resolve Dify client + user key for one conversation operation."""
    targets = await build_user_dify_targets(db, user)
    dify_user = await resolve_dify_user_for_conversation(
        db,
        user,
        conversation_id,
        dify_user_hint=dify_user_hint,
        server_hint=server_hint,
        mindbot_config_id_hint=mindbot_config_id_hint,
    )
    chosen = next((target for target in targets if target.dify_user == dify_user), None)
    if chosen is None and targets:
        chosen = targets[0]
    if chosen is None:
        client = await resolve_mindmate_dify_client(
            db,
            getattr(user, "organization_id", None),
        )
        return client, dify_user

    endpoint = await _resolve_endpoint_for_conversation(
        db,
        chosen,
        conversation_id,
        dify_user,
        server_hint=server_hint,
        mindbot_config_id_hint=mindbot_config_id_hint,
    )
    if endpoint is not None:
        return _client_for_endpoint(endpoint), dify_user

    client = await resolve_mindmate_dify_client(
        db,
        getattr(user, "organization_id", None),
    )
    return client, dify_user


async def resolve_client_for_dify_user(
    db: AsyncSession,
    user: User,
    *,
    dify_user: str,
    server_hint: Optional[int] = None,
    mindbot_config_id_hint: Optional[int] = None,
) -> Tuple[AsyncDifyClient, str]:
    """Resolve Dify client for operations keyed by ``dify_user`` (e.g. message feedback)."""
    targets = await build_user_dify_targets(db, user)
    hint = (dify_user or "").strip()
    if not hint:
        client = await resolve_mindmate_dify_client(
            db,
            getattr(user, "organization_id", None),
        )
        return client, mindmate_dify_user_id(user)

    chosen = next((target for target in targets if target.dify_user == hint), None)
    if chosen is None:
        client = await resolve_mindmate_dify_client(
            db,
            getattr(user, "organization_id", None),
        )
        return client, hint

    org_id = int(chosen.organization_id)
    if org_id <= 0:
        client = await resolve_mindmate_dify_client(db, None)
        return client, hint

    org = await _load_org(org_id)
    if org is None:
        client = await resolve_mindmate_dify_client(db, org_id)
        return client, hint

    if server_hint is not None or mindbot_config_id_hint is not None:
        endpoint = await resolve_endpoint_for_message_fetch(
            db,
            org,
            channel=chosen.channel,
            server=int(server_hint or 1),
            mindbot_config_id=mindbot_config_id_hint,
            dify_user=hint,
            strict_org=False,
        )
        if endpoint is not None:
            return _client_for_endpoint(endpoint), hint

    org_by_id = {org_id: org}
    endpoints = await _endpoints_for_target(db, chosen, org_by_id)
    if endpoints:
        preferred = endpoints[0]
        if server_hint is not None:
            for endpoint in endpoints:
                if int(endpoint.server) == int(server_hint):
                    preferred = endpoint
                    break
        return _client_for_endpoint(preferred), hint

    client = await resolve_mindmate_dify_client(db, org_id)
    return client, hint
