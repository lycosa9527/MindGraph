"""Upload lecture markdown to COS (or local fallback) and attach the key."""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from repositories.mind_classroom_repo import MindClassroomJobRepository
from services.mind_classroom.storage import delete_key, hydrate_local_from_cos, put_local_and_cos
from services.mind_classroom.storage_keys import (
    build_transcript_key,
    is_classroom_logical_key,
    normalize_transcript_mode,
)
from services.mind_classroom.transcript_md import render_transcript_markdown
from services.utils.error_types import DATABASE_ERRORS, FILE_IO_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)


def transcript_key_from_result(result_json: Any) -> Optional[str]:
    """Read a stored transcript key from result_json."""
    if not isinstance(result_json, dict):
        return None
    key = str(result_json.get("transcript_key") or "").strip()
    if key and is_classroom_logical_key(key):
        return key
    return None


def plan_transcript_replacement(
    *,
    current_job_id: str,
    keep_key: str,
    siblings: Sequence[tuple[str, Any]],
) -> tuple[list[str], list[tuple[str, dict[str, Any]]]]:
    """Collect superseded COS keys and result_json updates for older jobs."""
    stale_keys: list[str] = []
    seen: set[str] = set()
    updates: list[tuple[str, dict[str, Any]]] = []
    for sibling_id, result_json in siblings:
        if sibling_id == current_job_id or not isinstance(result_json, dict):
            continue
        old_key = transcript_key_from_result(result_json)
        if old_key and old_key != keep_key and old_key not in seen:
            seen.add(old_key)
            stale_keys.append(old_key)
        if not old_key:
            continue
        updated = dict(result_json)
        updated.pop("transcript_key", None)
        updated["transcript_replaced"] = True
        updates.append((sibling_id, updated))
    return stale_keys, updates


async def retire_superseded_transcripts(
    *,
    job_id: str,
    user_id: Optional[int],
    diagram_id: Optional[str],
    mode: str,
    keep_key: str,
) -> None:
    """Delete older lecture backups and drop their job pointers."""
    cleaned_diagram = (diagram_id or "").strip()
    if user_id is None or user_id <= 0 or not cleaned_diagram:
        return
    try:
        async with system_rls_session() as db:
            repo = MindClassroomJobRepository(db)
            rows = await repo.list_jobs_for_diagram(
                user_id=int(user_id),
                diagram_id=cleaned_diagram,
                mode=normalize_transcript_mode(mode),
            )
            siblings = [(row.id, row.result_json) for row in rows]
            stale_keys, updates = plan_transcript_replacement(
                current_job_id=job_id,
                keep_key=keep_key,
                siblings=siblings,
            )
            for sibling_id, result_json in updates:
                await repo.update_job(sibling_id, result_json=result_json, commit=False)
            if updates:
                await db.commit()
    except DATABASE_ERRORS as exc:
        logger.warning("[MindClassroom] Transcript replace lookup failed job=%s err=%s", job_id, exc)
        return
    for stale_key in stale_keys:
        try:
            await delete_key(stale_key)
        except FILE_IO_ERRORS as exc:
            logger.warning(
                "[MindClassroom] Old transcript delete failed job=%s key=%s err=%s",
                job_id,
                stale_key,
                exc,
            )


async def attach_transcript_md(
    *,
    job_id: str,
    settings: dict[str, Any],
    steps: list[dict[str, Any]],
    result_json: dict[str, Any],
    user_id: Optional[int] = None,
    diagram_id: Optional[str] = None,
) -> dict[str, Any]:
    """Write markdown, upload, replace any previous backup, and attach the key."""
    merged = dict(result_json)
    mode = str(settings.get("mode") or "canvas_tour")
    try:
        body = render_transcript_markdown(
            job_id=job_id,
            settings=settings,
            steps=steps,
            diagram_id=diagram_id or "",
        )
        key = build_transcript_key(
            job_id,
            user_id=user_id,
            diagram_id=diagram_id,
            mode=mode,
        )
        await put_local_and_cos(
            key,
            body.encode("utf-8"),
            content_type="text/markdown; charset=utf-8",
        )
        await retire_superseded_transcripts(
            job_id=job_id,
            user_id=user_id,
            diagram_id=diagram_id,
            mode=mode,
            keep_key=key,
        )
    except FILE_IO_ERRORS as exc:
        logger.warning("[MindClassroom] Transcript upload failed job=%s err=%s", job_id, exc)
        merged["transcript_uploaded"] = False
        return merged
    merged["transcript_key"] = key
    merged["transcript_uploaded"] = True
    return merged


async def ensure_transcript_on_server(result_json: Any) -> None:
    """Pull the markdown from COS onto this server when the local copy is gone."""
    key = transcript_key_from_result(result_json)
    if not key:
        return
    await hydrate_local_from_cos(key)
