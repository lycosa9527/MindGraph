"""Resolve the owning user for a classroom COS object."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.mind_classroom_repo import MindClassroomJobRepository, MindClassroomSlideRepository
from services.mind_classroom.storage_keys import (
    job_id_from_transcript_key,
    parse_diagram_transcript_key,
)


async def resolve_classroom_asset_owner_id(
    db: AsyncSession,
    logical_key: str,
) -> Optional[int]:
    """Return the job/slide owner, or None when the object is unknown."""
    job_id = job_id_from_transcript_key(logical_key)
    repo = MindClassroomJobRepository(db)
    if job_id:
        job = await repo.get_by_uuid(job_id)
        if job is None:
            return None
        return int(job.user_id)
    parsed = parse_diagram_transcript_key(logical_key)
    if parsed:
        user_id, diagram_id, mode = parsed
        job = await repo.latest_job_for_diagram(
            user_id=user_id,
            diagram_id=diagram_id,
            mode=mode,
        )
        if job is None:
            return None
        return int(job.user_id)
    slide = await MindClassroomSlideRepository(db).get_by_logical_key(logical_key)
    if slide is None:
        return None
    return int(slide.user_id)
