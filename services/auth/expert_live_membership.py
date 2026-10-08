"""
Move an expert's live presence and open rooms after a binding change.

The binding table updates immediately. WebSocket presence and Redis room
registries keep the school list from connect or room start, so a save has
to rewrite those copies or the old school keeps showing the expert.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.diagrams import Diagram
from models.domain.mindmate_collab import MindmateCollabSession
from routers.features.workshop_chat.dependencies import (
    access_channel,
    presence_org_ids_for_user,
)
from services.auth.expert_live_scope import (
    bound_org_label,
    parse_bound_org_label,
    session_registry_org_ids,
)
from services.auth.expert_school_binding import list_bound_org_ids
from services.features.mindmate_collab.redis_keys import (
    registry_global_org_key as mindmate_global_key,
)
from services.features.mindmate_collab.redis_keys import (
    registry_org_key as mindmate_org_key,
)
from services.features.mindmate_collab.redis_keys import (
    session_meta_key as mindmate_meta_key,
)
from services.features.mindmate_notify_ws_manager import mindmate_notify_ws_manager
from services.features.workshop_chat_ws_manager import chat_ws_manager
from services.online_collab.lifecycle.online_collab_visibility_helpers import (
    ONLINE_COLLAB_VISIBILITY_NETWORK,
    ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
    ONLINE_COLLAB_VISIBILITY_PRIVATE,
)
from services.online_collab.lifecycle.session_meta_cache import invalidate_session_meta
from services.online_collab.redis.online_collab_redis_keys import (
    registry_global_org_key as canvas_global_key,
)
from services.online_collab.redis.online_collab_redis_keys import (
    registry_org_key as canvas_org_key,
)
from services.online_collab.redis.online_collab_redis_keys import (
    session_meta_key as canvas_meta_key,
)
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import DATABASE_ERRORS, REDIS_ERRORS
from utils.auth.roles import is_expert
from utils.db.session_open import user_rls_session

logger = logging.getLogger(__name__)


def _meta_text(meta: dict, key: str) -> str:
    """Read one hash field as text."""
    raw = meta.get(key.encode())
    if raw is None:
        raw = meta.get(key)
    if isinstance(raw, (bytes, bytearray)):
        return raw.decode("utf-8", errors="replace")
    if isinstance(raw, memoryview):
        return bytes(raw).decode("utf-8", errors="replace")
    return "" if raw is None else str(raw)


async def refresh_expert_live_membership(user_ids: list[int]) -> None:
    """Rewrite presence and open-room registries for these experts."""
    seen: set[int] = set()
    for raw in user_ids:
        user_id = int(raw)
        if user_id <= 0 or user_id in seen:
            continue
        seen.add(user_id)
        try:
            await _refresh_one(user_id)
        except DATABASE_ERRORS + REDIS_ERRORS as exc:
            logger.warning("[ExpertLive] refresh failed user_id=%s: %s", user_id, exc)


async def _drop_closed_school_channels(db: AsyncSession, user: User) -> None:
    """Stop delivering channels this expert can no longer open."""
    user_id = int(user.id)
    subscribed = chat_ws_manager.subscribed_channel_ids(user_id)
    if not subscribed:
        return
    allowed: set[int] = set()
    for channel_id in subscribed:
        try:
            await access_channel(db, channel_id, user)
        except HTTPException:
            continue
        allowed.add(channel_id)
    if allowed != subscribed:
        chat_ws_manager.retain_channel_subscriptions(user_id, allowed)


async def _refresh_one(user_id: int) -> None:
    """Load current schools, then update sockets and Redis."""
    async with user_rls_session(user_id) as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user is None or not is_expert(user):
            return
        presence_ids = await presence_org_ids_for_user(db, user)
        bound = await list_bound_org_ids(db, user_id)
        canvas_codes = [
            str(code)
            for code in (
                await db.execute(
                    select(Diagram.workshop_code).where(
                        Diagram.user_id == user_id,
                        ~Diagram.is_deleted,
                        Diagram.workshop_code.isnot(None),
                        Diagram.workshop_visibility == ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
                    )
                )
            ).scalars()
            if code
        ]
        seminar_codes = [
            str(code)
            for code in (
                await db.execute(
                    select(MindmateCollabSession.code).where(
                        MindmateCollabSession.owner_user_id == user_id,
                        MindmateCollabSession.ended_at.is_(None),
                        MindmateCollabSession.visibility == ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
                    )
                )
            ).scalars()
            if code
        ]
        await _drop_closed_school_channels(db, user)

    await chat_ws_manager.replace_presence_orgs(user_id, presence_ids)
    await mindmate_notify_ws_manager.replace_presence_orgs(user_id, presence_ids)

    redis = get_async_redis()
    if not redis:
        return
    for code in canvas_codes:
        await _retarget_room(redis, code, "canvas", bound)
        invalidate_session_meta(code)
    for code in seminar_codes:
        await _retarget_room(redis, code, "mindmate", bound)


def _room_keys(kind: str, code: str) -> tuple[str, Any, str]:
    """Meta key, org-registry key function, and global registry key."""
    if kind == "canvas":
        return canvas_meta_key(code), canvas_org_key, canvas_global_key()
    return mindmate_meta_key(code), mindmate_org_key, mindmate_global_key()


async def _retarget_room(
    redis: Any,
    code: str,
    kind: str,
    bound_org_ids: list[int],
) -> None:
    """Point one live organization room at the expert's current schools."""
    meta_key, org_key, global_key = _room_keys(kind, code)
    try:
        meta = await redis.hgetall(meta_key) or {}
    except REDIS_ERRORS as exc:
        logger.warning("[ExpertLive] meta read failed code=%s: %s", code, exc)
        return
    if not meta:
        return
    visibility = _meta_text(meta, "visibility")
    if visibility in (ONLINE_COLLAB_VISIBILITY_NETWORK, ONLINE_COLLAB_VISIBILITY_PRIVATE):
        return
    host_raw = _meta_text(meta, "org_id")
    host_org_id = int(host_raw) if host_raw.isdigit() else None
    old_ids = set(session_registry_org_ids(host_org_id, parse_bound_org_label(_meta_text(meta, "bound_org_ids"))))
    new_ids = session_registry_org_ids(host_org_id, bound_org_ids)
    try:
        pipe = redis.pipeline(transaction=False)
        pipe.srem(global_key, code)
        for org_id in old_ids - set(new_ids):
            pipe.srem(org_key(org_id), code)
        for org_id in new_ids:
            if org_id not in old_ids:
                pipe.sadd(org_key(org_id), code)
        pipe.hset(meta_key, "bound_org_ids", bound_org_label(host_org_id, bound_org_ids))
        await pipe.execute()
    except REDIS_ERRORS as exc:
        logger.warning("[ExpertLive] registry move failed code=%s: %s", code, exc)
