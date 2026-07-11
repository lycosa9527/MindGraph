"""
PostgreSQL persistence for one-sentence panel turns.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from models.domain.auth import User
from models.domain.kitty_one_sentence import KittyOneSentenceTurn
from repositories.kitty_one_sentence_turn_repo import KittyOneSentenceTurnRepository
from services.kitty.session.one_sentence_command_detail import normalize_command_detail
from services.kitty.session.one_sentence_session_pg import (
    ensure_one_sentence_session,
    record_session_turn_metadata,
)
from services.kitty.session.one_sentence_turn_activity import schedule_one_sentence_turn_activity
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)


def _epoch_to_datetime(ts: int) -> datetime:
    try:
        return datetime.fromtimestamp(int(ts), tz=UTC)
    except (TypeError, ValueError, OSError):
        return datetime.now(UTC)


def turn_dict_to_row(
    *,
    user_id: int,
    organization_id: Optional[int],
    scope: str,
    session_id: Optional[str],
    turn: Dict[str, Any],
) -> KittyOneSentenceTurn:
    """Build an ORM row from a normalized Redis turn dict."""
    return KittyOneSentenceTurn(
        session_id=session_id,
        user_id=int(user_id),
        organization_id=int(organization_id) if organization_id is not None else None,
        scope=str(scope).strip(),
        turn_id=str(turn.get("turn_id") or "").strip(),
        role=str(turn.get("role") or "").strip(),
        content=str(turn.get("content") or "").strip(),
        phase=str(turn.get("phase") or "edit").strip(),
        source=str(turn.get("source") or "unknown").strip(),
        action=str(turn.get("action")).strip() if turn.get("action") else None,
        outcome=str(turn.get("outcome")).strip() if turn.get("outcome") else None,
        user_text=str(turn.get("user_text")).strip() if turn.get("user_text") else None,
        diagram_type=str(turn.get("diagram_type")).strip() if turn.get("diagram_type") else None,
        voice_session_id=str(turn.get("voice_session_id")).strip() if turn.get("voice_session_id") else None,
        request_id=str(turn.get("request_id")).strip() if turn.get("request_id") else None,
        command_detail=normalize_command_detail(turn.get("command_detail")),
        created_at=_epoch_to_datetime(int(turn.get("ts") or 0)),
    )


def serialize_turn_row(row: KittyOneSentenceTurn) -> Dict[str, Any]:
    """Serialize a PG row to the API turn dict shape."""
    created = row.created_at
    ts = int(created.timestamp()) if created is not None else 0
    payload: Dict[str, Any] = {
        "turn_id": row.turn_id,
        "ts": ts,
        "role": row.role,
        "content": row.content,
        "phase": row.phase,
        "source": row.source,
    }
    if row.action:
        payload["action"] = row.action
    if row.outcome:
        payload["outcome"] = row.outcome
    if row.user_text:
        payload["user_text"] = row.user_text
    if row.diagram_type:
        payload["diagram_type"] = row.diagram_type
    if row.voice_session_id:
        payload["voice_session_id"] = row.voice_session_id
    if row.request_id:
        payload["request_id"] = row.request_id
    if row.command_detail:
        payload["command_detail"] = row.command_detail
    if row.session_id:
        payload["session_id"] = row.session_id
    return payload


async def persist_one_sentence_turn_pg(
    *,
    user_id: int,
    organization_id: Optional[int],
    scope: str,
    turn: Dict[str, Any],
) -> bool:
    """Insert one turn into PostgreSQL (idempotent on scope+turn_id)."""
    turn_id = str(turn.get("turn_id") or "").strip()
    if not turn_id:
        return False
    org_id = organization_id
    if org_id is None:
        try:
            async with system_rls_session() as session:
                result = await session.execute(select(User.organization_id).where(User.id == int(user_id)).limit(1))
                org_scalar = result.scalar_one_or_none()
                if org_scalar is not None:
                    org_id = int(org_scalar)
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.debug("[OneSentencePG] org lookup failed user=%s: %s", user_id, exc)

    session_id = await ensure_one_sentence_session(
        user_id=user_id,
        organization_id=org_id,
        diagram_scope=scope,
        diagram_type=str(turn.get("diagram_type") or "") or None,
    )
    if not session_id:
        return False

    row = turn_dict_to_row(
        user_id=user_id,
        organization_id=org_id,
        scope=scope,
        session_id=session_id,
        turn=turn,
    )
    try:
        async with system_rls_session() as session:
            repo = KittyOneSentenceTurnRepository(session)
            inserted = await repo.insert_ignore_duplicate(row)
            if inserted:
                await session.commit()
                logger.info(
                    "[OneSentencePG] logged role=%s phase=%s request_id=%s scope=%s turn=%s session=%s",
                    row.role,
                    row.phase,
                    (row.request_id or "-")[:12],
                    scope[:16],
                    turn_id[:12],
                    (session_id or "-")[:12],
                )
                await record_session_turn_metadata(
                    session_id=session_id,
                    phase=str(turn.get("phase") or "edit"),
                    role=str(turn.get("role") or ""),
                    content=str(turn.get("content") or ""),
                    diagram_type=str(turn.get("diagram_type") or "") or None,
                    voice_session_id=str(turn.get("voice_session_id") or "") or None,
                )
                turn_with_session = {**turn, "session_id": session_id}
                schedule_one_sentence_turn_activity(
                    user_id=user_id,
                    organization_id=org_id,
                    scope=scope,
                    turn=turn_with_session,
                    session_id=session_id,
                )
            else:
                logger.debug(
                    "[OneSentencePG] duplicate skipped scope=%s turn=%s request_id=%s",
                    scope[:16],
                    turn_id[:12],
                    (row.request_id or "-")[:12],
                )
            return inserted
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning(
            "[OneSentencePG] persist failed scope=%s turn=%s: %s",
            scope[:16],
            turn_id[:12],
            exc,
        )
        return False


def schedule_one_sentence_turn_pg(
    *,
    user_id: int,
    organization_id: Optional[int],
    scope: str,
    turn: Dict[str, Any],
) -> None:
    """Fire-and-forget PostgreSQL persist for one turn."""
    asyncio.create_task(
        persist_one_sentence_turn_pg(
            user_id=user_id,
            organization_id=organization_id,
            scope=scope,
            turn=turn,
        )
    )


async def list_one_sentence_turns_pg(
    *,
    scope: str,
    user_id: int,
    limit: int,
    session_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Load turns oldest-first from PostgreSQL."""
    try:
        async with system_rls_session() as session:
            repo = KittyOneSentenceTurnRepository(session)
            if session_id:
                rows = await repo.list_for_session(
                    session_id=session_id,
                    user_id=user_id,
                    limit=limit,
                )
            else:
                rows = await repo.list_for_scope(scope=scope, user_id=user_id, limit=limit)
            return [serialize_turn_row(row) for row in rows]
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[OneSentencePG] list failed scope=%s: %s", scope[:16], exc)
        return []


async def list_one_sentence_diagram_activity_pg(
    *,
    diagram_id: str,
    user_id: int,
    limit: int = 100,
    actions_only: bool = True,
) -> List[Dict[str, Any]]:
    """Load diagram-scoped activity rows (node actions) from PostgreSQL."""
    try:
        async with system_rls_session() as session:
            repo = KittyOneSentenceTurnRepository(session)
            rows = await repo.list_for_diagram_id(
                diagram_id=diagram_id,
                user_id=user_id,
                limit=limit,
                actions_only=actions_only,
            )
            return [serialize_turn_row(row) for row in rows]
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning(
            "[OneSentencePG] diagram activity list failed diagram=%s: %s",
            str(diagram_id)[:16],
            exc,
        )
        return []
