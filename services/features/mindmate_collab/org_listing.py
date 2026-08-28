"""
Org-visible MindMate collab room listing (SQL + Redis merge).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from sqlalchemy import select

from models.domain.auth import User
from models.domain.mindmate_collab import MindmateCollabSession
from services.features.mindmate_collab.redis_keys import (
    normalize_collab_code,
    registry_global_org_key,
    registry_org_key,
    session_meta_key,
)
from services.online_collab.lifecycle.online_collab_expiry import is_online_collab_expired
from services.online_collab.lifecycle.online_collab_visibility_helpers import (
    ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
)
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS
from utils.db.session_open import user_rls_session

logger = logging.getLogger(__name__)

ParticipantCountsFn = Callable[[List[str]], Awaitable[Dict[str, int]]]


def _decode_text(value: Any) -> str:
    """Decode Redis bytes / memoryview to str."""
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, memoryview):
        return bytes(value).decode("utf-8", errors="replace")
    return str(value) if value is not None else ""


def _decode_code_set(raw: Any) -> set[str]:
    """Normalize a Redis SET of room codes."""
    if not raw:
        return set()
    return {normalize_collab_code(_decode_text(item)) for item in raw if item}


def merge_org_session_rows(
    sql_rows: List[Dict[str, Any]],
    redis_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """SQL rows win on conflict; Redis fills colleagues hidden by incomplete RLS."""
    by_code: Dict[str, Dict[str, Any]] = {}
    for row in redis_rows:
        by_code[normalize_collab_code(str(row.get("code") or ""))] = row
    ordered: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for row in sql_rows:
        key = normalize_collab_code(str(row.get("code") or ""))
        if not key or key in seen:
            continue
        by_code[key] = row
        ordered.append(row)
        seen.add(key)
    for key, row in by_code.items():
        if key and key not in seen:
            ordered.append(row)
            seen.add(key)
    return ordered


async def resolve_viewer_org_id(
    user_id: int,
    organization_id: Optional[int],
) -> Optional[int]:
    """Return the viewer's org id from the caller, else a user-scoped probe."""
    if organization_id is not None:
        return int(organization_id)
    async with user_rls_session(user_id) as probe:
        viewer = (await probe.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not viewer or viewer.organization_id is None:
            return None
        return int(viewer.organization_id)


def _session_dict(
    *,
    session_id: str,
    code: str,
    title: str,
    owner_name: str,
    owner_user_id: int,
    participant_count: int,
    visibility: str,
) -> Dict[str, Any]:
    """Build the REST payload for one org seminar row."""
    return {
        "session_id": session_id,
        "code": code,
        "title": title,
        "owner_name": owner_name,
        "owner_user_id": owner_user_id,
        "participant_count": participant_count,
        "visibility": visibility,
    }


async def list_org_sessions_sql(user_id: int, org_id: int) -> List[Dict[str, Any]]:
    """List live org rooms under user RLS with app.organization_id bound."""
    async with user_rls_session(user_id, organization_id=org_id) as db:
        result = await db.execute(
            select(MindmateCollabSession, User.name, User.phone, User.email)
            .outerjoin(User, User.id == MindmateCollabSession.owner_user_id)
            .where(
                MindmateCollabSession.organization_id == org_id,
                MindmateCollabSession.visibility == ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
                MindmateCollabSession.ended_at.is_(None),
            )
            .order_by(MindmateCollabSession.started_at.desc()),
        )
        rows = result.all()

    sessions: List[Dict[str, Any]] = []
    for session, owner_name, owner_phone, owner_email in rows:
        if session.expires_at and is_online_collab_expired(session.expires_at):
            continue
        display = owner_name or owner_phone or owner_email or str(session.owner_user_id)
        sessions.append(
            _session_dict(
                session_id=session.id,
                code=session.code,
                title=session.title,
                owner_name=display,
                owner_user_id=session.owner_user_id,
                participant_count=0,
                visibility=session.visibility,
            ),
        )
    return sessions


def _redis_row_from_meta(code: str, meta: Dict[str, str], now: int) -> Optional[Dict[str, Any]]:
    """Map Redis session HASH to a list row, or None when not joinable."""
    visibility = meta.get("visibility") or ONLINE_COLLAB_VISIBILITY_ORGANIZATION
    if visibility != ONLINE_COLLAB_VISIBILITY_ORGANIZATION:
        return None
    expires_raw = meta.get("expires_at") or ""
    if expires_raw:
        try:
            if int(expires_raw) <= now:
                return None
        except (TypeError, ValueError):
            pass
    owner_raw = meta.get("owner_id") or "0"
    try:
        owner_user_id = int(owner_raw)
    except (TypeError, ValueError):
        owner_user_id = 0
    session_id = meta.get("session_id") or ""
    if not session_id:
        return None
    return _session_dict(
        session_id=session_id,
        code=code,
        title=meta.get("title") or "MindMate Collab",
        owner_name=meta.get("owner_name") or str(owner_user_id),
        owner_user_id=owner_user_id,
        participant_count=0,
        visibility=visibility,
    )


async def list_org_sessions_redis(org_id: int) -> List[Dict[str, Any]]:
    """List live org rooms from Redis registries (includes empty host-only rooms)."""
    redis = get_async_redis()
    if not redis:
        return []
    try:
        pipe = redis.pipeline(transaction=False)
        pipe.smembers(registry_org_key(org_id))
        pipe.smembers(registry_global_org_key())
        org_raw, global_raw = await pipe.execute()
    except REDIS_ERRORS as exc:
        logger.warning("[MindmateCollab] org registry SMEMBERS failed org_id=%s: %s", org_id, exc)
        return []

    codes = sorted(_decode_code_set(org_raw) | _decode_code_set(global_raw))
    if not codes:
        return []

    try:
        pipe = redis.pipeline(transaction=False)
        for code in codes:
            pipe.hgetall(session_meta_key(code))
        metas = await pipe.execute()
    except REDIS_ERRORS as exc:
        logger.warning("[MindmateCollab] org session meta pipeline failed org_id=%s: %s", org_id, exc)
        return []

    now = int(time.time())
    sessions: List[Dict[str, Any]] = []
    for code, meta_raw in zip(codes, metas):
        if not isinstance(meta_raw, dict) or not meta_raw:
            continue
        meta = {_decode_text(key): _decode_text(val) for key, val in meta_raw.items()}
        row = _redis_row_from_meta(code, meta, now)
        if row:
            sessions.append(row)
    return sessions


async def attach_participant_counts(
    rows: List[Dict[str, Any]],
    participant_counts_fn: ParticipantCountsFn,
) -> List[Dict[str, Any]]:
    """Fill participant_count from Redis HLEN for each room code."""
    codes = [str(row.get("code") or "") for row in rows if row.get("code")]
    counts = await participant_counts_fn(codes)
    for row in rows:
        code = normalize_collab_code(str(row.get("code") or ""))
        row["participant_count"] = counts.get(code, 0)
    return rows


async def list_visible_org_sessions(
    user_id: int,
    *,
    organization_id: Optional[int],
    participant_counts_fn: ParticipantCountsFn,
) -> List[Dict[str, Any]]:
    """Return live org seminars the viewer should see in the school group list."""
    org_id = await resolve_viewer_org_id(user_id, organization_id)
    if org_id is None:
        return []
    sql_rows = await list_org_sessions_sql(user_id, org_id)
    redis_rows = await list_org_sessions_redis(org_id)
    merged = merge_org_session_rows(sql_rows, redis_rows)
    return await attach_participant_counts(merged, participant_counts_fn)
