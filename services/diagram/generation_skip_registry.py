"""Redis + PostgreSQL registry for generate_dingtalk preview outcomes."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.generation_preview_link import GenerationPreviewLink
from repositories.generation_preview_link_repo import GenerationPreviewLinkRepository
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_PREVIEW_DB_ERRORS: tuple[type[BaseException], ...] = (*DATABASE_ERRORS, *BACKGROUND_INFRA_ERRORS)

GEN_LIB_SKIP_PREFIX = "mg:gen_lib_skip:"
GEN_LIB_SKIP_TTL_SECONDS = 86400


def _skip_key(unique_id: str) -> str:
    return f"{GEN_LIB_SKIP_PREFIX}{(unique_id or '').strip()[:32]}"


def _parse_outcome(raw: str) -> Optional[dict[str, Any]]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    reason_raw = data.get("reason")
    reason = reason_raw.strip() if isinstance(reason_raw, str) else ""
    lang_raw = data.get("language")
    language = lang_raw.strip() if isinstance(lang_raw, str) and lang_raw.strip() else "zh"
    diagram_raw = data.get("diagram_id")
    diagram_id = diagram_raw.strip() if isinstance(diagram_raw, str) and diagram_raw.strip() else ""
    dtype_raw = data.get("diagram_type")
    diagram_type = dtype_raw.strip() if isinstance(dtype_raw, str) else ""
    title_raw = data.get("title")
    title = title_raw.strip() if isinstance(title_raw, str) else ""
    spec = data.get("spec")
    spec_dict = spec if isinstance(spec, dict) else None
    return {
        "reason": reason,
        "language": language,
        "diagram_id": diagram_id,
        "diagram_type": diagram_type,
        "title": title,
        "spec": spec_dict,
    }


def _outcome_from_link_row(row: GenerationPreviewLink) -> dict[str, Any]:
    diagram_raw = row.diagram_id
    diagram_id = diagram_raw.strip() if isinstance(diagram_raw, str) and diagram_raw.strip() else ""
    return {
        "reason": (row.skip_reason or "").strip(),
        "language": (row.language or "zh").strip() or "zh",
        "diagram_id": diagram_id,
        "diagram_type": (row.diagram_type or "").strip(),
        "title": (row.title or "").strip(),
        "spec": row.spec if isinstance(row.spec, dict) else None,
    }


async def _load_preview_outcome_from_db(unique_id: str) -> Optional[dict[str, Any]]:
    uid = (unique_id or "").strip()[:8]
    if not uid:
        return None
    try:
        async with system_rls_session() as db:
            repo = GenerationPreviewLinkRepository(db)
            row = await repo.get_by_preview_id(uid)
            if row is None:
                return None
            return _outcome_from_link_row(row)
    except _PREVIEW_DB_ERRORS as exc:
        logger.warning(
            "[GenerateDingTalk] load preview outcome from DB failed id=%s: %s",
            uid,
            exc,
        )
        return None


async def _persist_preview_outcome_to_db(
    db: AsyncSession,
    unique_id: str,
    *,
    reason: Optional[str],
    language: str,
    diagram_id: Optional[str],
    diagram_type: str,
    title: str,
    spec: Optional[dict[str, Any]],
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
) -> None:
    repo = GenerationPreviewLinkRepository(db)
    await repo.upsert_outcome(
        unique_id,
        skip_reason=(reason or "").strip(),
        language=language,
        diagram_id=diagram_id,
        user_id=user_id,
        organization_id=organization_id,
        diagram_type=diagram_type,
        title=title,
        spec=spec,
    )


async def store_generation_preview_outcome(
    unique_id: str,
    *,
    reason: Optional[str] = None,
    language: str,
    diagram_id: Optional[str] = None,
    diagram_type: str = "",
    title: str = "",
    spec: Optional[dict[str, Any]] = None,
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    db: Optional[AsyncSession] = None,
) -> bool:
    """Record save outcome for a temp dingtalk PNG id (Redis cache + durable PostgreSQL)."""
    uid = (unique_id or "").strip()
    if not uid:
        return False
    payload_obj: dict[str, Any] = {
        "reason": (reason or "").strip()[:64],
        "language": (language or "zh").strip()[:16],
        "diagram_id": (diagram_id or "").strip()[:64],
        "diagram_type": (diagram_type or "").strip()[:64],
        "title": (title or "").strip()[:200],
    }
    if spec is not None:
        payload_obj["spec"] = spec
    payload = json.dumps(payload_obj, separators=(",", ":"))

    redis_ok = False
    redis = get_async_redis()
    if redis is not None:
        try:
            await redis.set(_skip_key(uid), payload, ex=GEN_LIB_SKIP_TTL_SECONDS)
            redis_ok = True
        except RedisError as exc:
            logger.warning(
                "[GenerateDingTalk] store_generation_preview_outcome failed id=%s: %s",
                uid,
                exc,
            )

    db_ok = False
    if db is not None:
        try:
            await _persist_preview_outcome_to_db(
                db,
                uid,
                reason=reason,
                language=language,
                diagram_id=diagram_id,
                diagram_type=diagram_type,
                title=title,
                spec=spec,
                user_id=user_id,
                organization_id=organization_id,
            )
            db_ok = True
        except _PREVIEW_DB_ERRORS as exc:
            logger.warning(
                "[GenerateDingTalk] persist preview outcome to DB failed id=%s: %s",
                uid,
                exc,
            )

    return redis_ok or db_ok


async def store_generation_library_skip(
    unique_id: str,
    *,
    reason: str,
    language: str,
) -> bool:
    """Backward-compatible skip-only store."""
    return await store_generation_preview_outcome(
        unique_id,
        reason=reason,
        language=language,
    )


async def get_generation_preview_outcome(unique_id: str) -> Optional[dict[str, Any]]:
    """Return outcome payload from Redis, falling back to PostgreSQL."""
    uid = (unique_id or "").strip()
    if not uid:
        return None
    redis = get_async_redis()
    if redis is not None:
        try:
            raw = await redis.get(_skip_key(uid))
        except RedisError as exc:
            logger.warning(
                "[GenerateDingTalk] get_generation_preview_outcome failed id=%s: %s",
                uid,
                exc,
            )
        else:
            if isinstance(raw, str) and raw.strip():
                parsed = _parse_outcome(raw)
                if parsed is not None:
                    return parsed
    return await _load_preview_outcome_from_db(uid)


async def get_generation_library_skip(unique_id: str) -> Optional[dict[str, str]]:
    """Backward-compatible skip lookup (reason + language only)."""
    data = await get_generation_preview_outcome(unique_id)
    if data is None:
        return None
    reason = data.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        diagram_id = data.get("diagram_id")
        if isinstance(diagram_id, str) and diagram_id.strip():
            return {
                "reason": "",
                "language": str(data.get("language") or "zh"),
                "diagram_id": diagram_id.strip(),
            }
        return None
    language = data.get("language")
    lang = language if isinstance(language, str) and language.strip() else "zh"
    result: dict[str, str] = {"reason": reason.strip(), "language": lang.strip()}
    diagram_id = data.get("diagram_id")
    if isinstance(diagram_id, str) and diagram_id.strip():
        result["diagram_id"] = diagram_id.strip()
    return result


async def update_generation_preview_diagram_id(unique_id: str, diagram_id: str) -> bool:
    """Set diagram_id after a successful MindMate reclaim."""
    uid = (unique_id or "").strip()
    did = (diagram_id or "").strip()
    if not uid or not did:
        return False
    existing = await get_generation_preview_outcome(uid)
    if existing is None:
        return False

    db_ok = False
    try:
        async with system_rls_session() as db:
            repo = GenerationPreviewLinkRepository(db)
            db_ok = await repo.set_diagram_id(uid, did)
    except _PREVIEW_DB_ERRORS as exc:
        logger.warning(
            "[GenerateDingTalk] update preview diagram id in DB failed id=%s: %s",
            uid,
            exc,
        )

    redis_ok = await store_generation_preview_outcome(
        uid,
        reason="",
        language=str(existing.get("language") or "zh"),
        diagram_id=did,
        diagram_type=str(existing.get("diagram_type") or ""),
        title=str(existing.get("title") or ""),
    )
    return redis_ok or db_ok
