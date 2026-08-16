"""Upload lecture markdown to COS (or local fallback) and attach the key."""

from __future__ import annotations

import logging
from typing import Any, Optional

from services.mind_classroom.storage import hydrate_local_from_cos, put_local_and_cos
from services.mind_classroom.storage_keys import (
    build_transcript_key,
    is_classroom_logical_key,
)
from services.mind_classroom.transcript_md import render_transcript_markdown
from services.utils.error_types import FILE_IO_ERRORS

logger = logging.getLogger(__name__)


def transcript_key_from_result(result_json: Any) -> Optional[str]:
    """Read a stored transcript key from result_json."""
    if not isinstance(result_json, dict):
        return None
    key = str(result_json.get("transcript_key") or "").strip()
    if key and is_classroom_logical_key(key):
        return key
    return None


async def attach_transcript_md(
    *,
    job_id: str,
    settings: dict[str, Any],
    steps: list[dict[str, Any]],
    result_json: dict[str, Any],
) -> dict[str, Any]:
    """Write markdown, upload, and return result_json with transcript_key when possible."""
    merged = dict(result_json)
    try:
        body = render_transcript_markdown(job_id=job_id, settings=settings, steps=steps)
        key = build_transcript_key(job_id)
        await put_local_and_cos(
            key,
            body.encode("utf-8"),
            content_type="text/markdown; charset=utf-8",
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
