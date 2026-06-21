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
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clients.dify import AsyncDifyClient
from models.domain.auth import Organization, User
from services.dify.export.endpoints import endpoints_for_target
from services.dify.export.target_resolution import build_user_dify_targets
from services.dify.export.types import UserTarget
from services.dify.org_mindmate_client import resolve_mindmate_dify_client
from services.utils.error_types import DIFY_API_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

DEFAULT_LIST_TIMEOUT = int(os.getenv("DIFY_TIMEOUT", "300"))


@dataclass(frozen=True)
class UnifiedConversation:
    """One conversation row in the merged web + MindBot history list."""

    id: str
    name: str
    created_at: int
    updated_at: int
    channel: str
    dify_user: str


async def _load_org(org_id: int) -> Optional[Organization]:
    async with system_rls_session() as db:
        return (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()


async def client_for_target(db: AsyncSession, target: UserTarget) -> AsyncDifyClient:
    """Resolve the Dify Service API client for one user identity."""
    org_id = int(target.organization_id)
    if target.channel == "web" or org_id <= 0:
        return await resolve_mindmate_dify_client(db, org_id if org_id > 0 else None)

    org = await _load_org(org_id)
    if org is None:
        return await resolve_mindmate_dify_client(db, org_id)

    endpoint_items = await endpoints_for_target(
        org,
        channel=target.channel,
        dify_user=target.dify_user,
        db=db,
        strict_org=False,
    )
    if endpoint_items:
        endpoint = endpoint_items[0]
        return AsyncDifyClient(
            api_key=endpoint.api_key,
            api_url=endpoint.api_url,
            timeout=DEFAULT_LIST_TIMEOUT,
        )
    return await resolve_mindmate_dify_client(db, org_id)


def _conv_to_unified(item: dict, target: UserTarget) -> Optional[UnifiedConversation]:
    conv_id = str(item.get("id") or "").strip()
    if not conv_id:
        return None
    created = int(item.get("created_at") or 0)
    updated = int(item.get("updated_at") or created)
    return UnifiedConversation(
        id=conv_id,
        name=str(item.get("name") or ""),
        created_at=created,
        updated_at=updated,
        channel=target.channel,
        dify_user=target.dify_user,
    )


async def list_unified_conversations(
    db: AsyncSession,
    user: User,
    *,
    limit: int = 20,
    last_id: Optional[str] = None,
) -> Tuple[List[UnifiedConversation], bool]:
    """
    List conversations across web MindMate and bound MindBot Dify user keys.

    Fetches up to ``limit`` rows per identity, merges by ``updated_at``, and
    returns the newest ``limit`` rows. ``last_id`` is accepted for API compat but
    merged pagination uses conversation id only when a single web identity exists.
    """
    targets = await build_user_dify_targets(db, user)
    if len(targets) == 1 and last_id:
        target = targets[0]
        client = await client_for_target(db, target)
        result = await client.get_conversations(
            user_id=target.dify_user,
            last_id=last_id,
            limit=limit,
            sort_by="-updated_at",
        )
        rows = [
            unified
            for item in (result.get("data") or [])
            if isinstance(item, dict)
            for unified in [_conv_to_unified(item, target)]
            if unified is not None
        ]
        return rows, bool(result.get("has_more", False))

    merged: dict[str, UnifiedConversation] = {}
    any_has_more = False
    page_size = max(1, min(limit, 100))

    for target in targets:
        try:
            client = await client_for_target(db, target)
            result = await client.get_conversations(
                user_id=target.dify_user,
                limit=page_size,
                sort_by="-updated_at",
            )
        except DIFY_API_ERRORS as exc:
            logger.warning(
                "[UnifiedConversations] list failed user=%s channel=%s: %s",
                target.dify_user,
                target.channel,
                exc,
            )
            continue

        if result.get("has_more"):
            any_has_more = True

        for item in result.get("data") or []:
            if not isinstance(item, dict):
                continue
            unified = _conv_to_unified(item, target)
            if unified is None:
                continue
            key = f"{unified.dify_user}:{unified.id}"
            existing = merged.get(key)
            if existing is None or unified.updated_at >= existing.updated_at:
                merged[key] = unified

    ordered = sorted(merged.values(), key=lambda row: row.updated_at, reverse=True)
    page = ordered[:page_size]
    has_more = any_has_more or len(ordered) > page_size
    return page, has_more


async def resolve_dify_user_for_conversation(
    db: AsyncSession,
    user: User,
    conversation_id: str,
    *,
    dify_user_hint: Optional[str] = None,
) -> str:
    """Pick the Dify ``user`` string that owns ``conversation_id``."""
    targets = await build_user_dify_targets(db, user)
    if dify_user_hint:
        hint = dify_user_hint.strip()
        for target in targets:
            if target.dify_user == hint:
                return hint

    web_targets = [target for target in targets if target.channel == "web"]
    if web_targets:
        return web_targets[0].dify_user

    for target in targets:
        try:
            client = await client_for_target(db, target)
            result = await client.get_messages(
                conversation_id=conversation_id,
                user_id=target.dify_user,
                limit=1,
            )
            if result.get("data"):
                return target.dify_user
        except DIFY_API_ERRORS:
            continue

    return targets[0].dify_user if targets else ""


async def resolve_client_and_dify_user(
    db: AsyncSession,
    user: User,
    conversation_id: str,
    *,
    dify_user_hint: Optional[str] = None,
) -> Tuple[AsyncDifyClient, str]:
    """Resolve Dify client + user key for one conversation operation."""
    targets = await build_user_dify_targets(db, user)
    dify_user = await resolve_dify_user_for_conversation(
        db,
        user,
        conversation_id,
        dify_user_hint=dify_user_hint,
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
    client = await client_for_target(db, chosen)
    return client, dify_user
