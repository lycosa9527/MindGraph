"""
PostgreSQL session registry for one-sentence panel flows.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import update

from models.domain.kitty_one_sentence import KittyOneSentenceSession, KittyOneSentenceTurn
from repositories.kitty_one_sentence_session_repo import KittyOneSentenceSessionRepository
from services.kitty.infra.scope.kitty_scope_access import scope_looks_like_library_uuid
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)


def serialize_session_row(row: KittyOneSentenceSession) -> Dict[str, Any]:
    """Serialize a session for REST/analytics consumers."""
    created = row.created_at
    updated = row.updated_at
    last_activity = row.last_activity_at
    return {
        "session_id": row.id,
        "user_id": int(row.user_id),
        "organization_id": int(row.organization_id) if row.organization_id is not None else None,
        "diagram_scope": row.diagram_scope,
        "diagram_id": row.diagram_id,
        "diagram_type": row.diagram_type,
        "status": row.status,
        "turn_count": int(row.turn_count),
        "create_turn_count": int(row.create_turn_count),
        "edit_turn_count": int(row.edit_turn_count),
        "first_prompt_preview": row.first_prompt_preview,
        "last_voice_session_id": row.last_voice_session_id,
        "created_at": created.isoformat() if created is not None else None,
        "updated_at": updated.isoformat() if updated is not None else None,
        "last_activity_at": last_activity.isoformat() if last_activity is not None else None,
    }


def _diagram_id_from_scope(scope: str) -> Optional[str]:
    cleaned = str(scope or "").strip()
    if scope_looks_like_library_uuid(cleaned):
        return cleaned
    return None


async def ensure_one_sentence_session(
    *,
    user_id: int,
    organization_id: Optional[int],
    diagram_scope: str,
    diagram_type: Optional[str] = None,
) -> Optional[str]:
    """
    Return stable session_id for this user + diagram scope.

    Creates the session row on first turn; subsequent turns reuse the same id.
    """
    scope = str(diagram_scope or "").strip()
    if not scope or user_id <= 0:
        return None

    now = datetime.now(UTC)
    diagram_id = _diagram_id_from_scope(scope)
    try:
        async with system_rls_session() as session:
            repo = KittyOneSentenceSessionRepository(session)
            existing = await repo.get_by_user_scope(user_id=user_id, diagram_scope=scope)
            if existing is not None:
                if diagram_type and not existing.diagram_type:
                    existing.diagram_type = diagram_type
                    existing.updated_at = now
                await session.commit()
                return existing.id

            session_id = str(uuid.uuid4())
            row = KittyOneSentenceSession(
                id=session_id,
                user_id=int(user_id),
                organization_id=int(organization_id) if organization_id is not None else None,
                diagram_scope=scope,
                diagram_id=diagram_id,
                diagram_type=(diagram_type or "").strip()[:50] or None,
                status="active",
                turn_count=0,
                create_turn_count=0,
                edit_turn_count=0,
                created_at=now,
                updated_at=now,
                last_activity_at=now,
            )
            await repo.insert(row)
            await session.commit()
            return session_id
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning(
            "[OneSentenceSession] ensure failed user=%s scope=%s: %s",
            user_id,
            scope[:16],
            exc,
        )
        return None


async def get_one_sentence_session(
    *,
    session_id: str,
    user_id: int,
) -> Optional[Dict[str, Any]]:
    """Load one session summary for the owner."""
    try:
        async with system_rls_session() as session:
            repo = KittyOneSentenceSessionRepository(session)
            row = await repo.get_by_id(session_id, user_id=user_id)
            if row is None:
                return None
            return serialize_session_row(row)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[OneSentenceSession] get failed id=%s: %s", session_id[:16], exc)
        return None


async def list_one_sentence_sessions(
    *,
    user_id: int,
    limit: int = 50,
    before_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List trackable sessions newest-first (analytics / admin-ready)."""
    try:
        async with system_rls_session() as session:
            repo = KittyOneSentenceSessionRepository(session)
            rows = await repo.list_for_user(user_id=user_id, limit=limit, before_id=before_id)
            return [serialize_session_row(row) for row in rows]
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[OneSentenceSession] list failed user=%s: %s", user_id, exc)
        return []


async def record_session_turn_metadata(
    *,
    session_id: str,
    phase: str,
    role: str,
    content: str,
    diagram_type: Optional[str],
    voice_session_id: Optional[str],
) -> None:
    """Update session counters after a turn is stored."""
    try:
        async with system_rls_session() as session:
            repo = KittyOneSentenceSessionRepository(session)
            await repo.touch_after_turn(
                session_id,
                phase=phase,
                role=role,
                content=content,
                diagram_type=diagram_type,
                voice_session_id=voice_session_id,
            )
            await session.commit()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.debug("[OneSentenceSession] touch failed id=%s: %s", session_id[:16], exc)


async def migrate_one_sentence_scope_pg(
    *,
    user_id: int,
    from_scope: str,
    to_scope: str,
) -> bool:
    """
    Move session registry and turns from ephemeral scope to saved diagram scope.

    Merges into an existing target session when the user reopens a saved diagram.
    """
    source_scope = str(from_scope or "").strip()
    target_scope = str(to_scope or "").strip()
    if not source_scope or not target_scope or source_scope == target_scope:
        return True
    if user_id <= 0:
        return False

    now = datetime.now(UTC)
    target_diagram_id = _diagram_id_from_scope(target_scope)
    try:
        async with system_rls_session() as session:
            repo = KittyOneSentenceSessionRepository(session)
            source_row = await repo.get_by_user_scope(user_id=user_id, diagram_scope=source_scope)
            if source_row is None:
                await session.execute(
                    update(KittyOneSentenceTurn)
                    .where(
                        KittyOneSentenceTurn.user_id == user_id,
                        KittyOneSentenceTurn.scope == source_scope,
                    )
                    .values(scope=target_scope)
                )
                await session.commit()
                return True

            target_row = await repo.get_by_user_scope(user_id=user_id, diagram_scope=target_scope)
            if target_row is None:
                source_row.diagram_scope = target_scope
                source_row.diagram_id = target_diagram_id
                source_row.updated_at = now
                await session.execute(
                    update(KittyOneSentenceTurn)
                    .where(
                        KittyOneSentenceTurn.user_id == user_id,
                        KittyOneSentenceTurn.scope == source_scope,
                    )
                    .values(scope=target_scope)
                )
            else:
                target_row.turn_count = int(target_row.turn_count) + int(source_row.turn_count)
                target_row.create_turn_count = int(target_row.create_turn_count) + int(source_row.create_turn_count)
                target_row.edit_turn_count = int(target_row.edit_turn_count) + int(source_row.edit_turn_count)
                if not target_row.first_prompt_preview and source_row.first_prompt_preview:
                    target_row.first_prompt_preview = source_row.first_prompt_preview
                if not target_row.diagram_type and source_row.diagram_type:
                    target_row.diagram_type = source_row.diagram_type
                if source_row.last_activity_at and (
                    target_row.last_activity_at is None or source_row.last_activity_at > target_row.last_activity_at
                ):
                    target_row.last_activity_at = source_row.last_activity_at
                target_row.updated_at = now
                await session.execute(
                    update(KittyOneSentenceTurn)
                    .where(
                        KittyOneSentenceTurn.user_id == user_id,
                        KittyOneSentenceTurn.scope == source_scope,
                    )
                    .values(scope=target_scope, session_id=target_row.id)
                )
                await session.delete(source_row)

            await session.commit()
            return True
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning(
            "[OneSentenceSession] migrate failed user=%s %s->%s: %s",
            user_id,
            source_scope[:16],
            target_scope[:16],
            exc,
        )
        return False
