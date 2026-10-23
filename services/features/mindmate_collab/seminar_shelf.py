"""Move a chat file or shared diagram onto the seminar resource or artifact shelf."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from models.domain.auth import User
from models.domain.mindmate_collab import MindmateCollabBackgroundFile, MindmateCollabSession
from services.features.mindmate_collab.background_files import (
    DIAGRAM_REF_TYPE,
    MAX_BACKGROUND_FILES,
    get_background_file,
    store_background_bytes,
)
from services.features.mindmate_collab.share_canvas import (
    normalize_canvas_diagram_id,
    session_contains_canvas_diagram,
)
from services.features.mindmate_collab.ws_broadcast import broadcast_to_all
from utils.db.session_open import system_rls_session


def shelf_flags(destination: str) -> tuple[bool, bool]:
    """Return ``(listed, artifact)`` for one shelf destination."""
    if destination == "resource":
        return True, False
    if destination == "artifact":
        return False, True
    raise ValueError("file_type")


def shelf_title(raw: str) -> str:
    """Keep a diagram caption as a folder filename."""
    cleaned = " ".join((raw or "").replace("\x00", "").split())
    if not cleaned:
        cleaned = "MindGraph"
    return cleaned[:180]


async def shelve_seminar_item(
    session: MindmateCollabSession,
    user: User,
    *,
    kind: str,
    destination: str,
    file_id: str = "",
    diagram_id: str = "",
    title: str = "",
) -> dict[str, object]:
    """Place one chat file or shared diagram on the chosen shelf."""
    listed, artifact = shelf_flags(destination)
    if kind == "file":
        payload = await _shelve_existing_file(session.id, file_id, listed=listed, artifact=artifact)
    elif kind == "diagram":
        payload = await _shelve_diagram(
            session,
            user,
            diagram_id,
            title,
            listed=listed,
            artifact=artifact,
        )
    else:
        raise ValueError("file_type")
    actor_name = (getattr(user, "name", None) or getattr(user, "username", None) or "").strip()
    await broadcast_to_all(
        session.code,
        {
            "type": "seminar_shelf",
            "destination": destination,
            "file": payload,
            "actor_user_id": int(user.id),
            "actor_name": actor_name,
        },
    )
    return payload


async def _shelf_count(session_id: str, *, artifact: bool) -> int:
    column = MindmateCollabBackgroundFile.artifact if artifact else MindmateCollabBackgroundFile.listed
    async with system_rls_session() as db:
        count = await db.scalar(
            select(func.count())
            .select_from(MindmateCollabBackgroundFile)
            .where(
                MindmateCollabBackgroundFile.session_id == session_id,
                column.is_(True),
            )
        )
    return int(count or 0)


async def _ensure_room(
    session_id: str,
    *,
    entering_listed: bool,
    entering_artifact: bool,
    already_listed: bool,
    already_artifact: bool,
) -> None:
    if entering_listed and not already_listed:
        if await _shelf_count(session_id, artifact=False) >= MAX_BACKGROUND_FILES:
            raise ValueError("file_limit")
    if entering_artifact and not already_artifact:
        if await _shelf_count(session_id, artifact=True) >= MAX_BACKGROUND_FILES:
            raise ValueError("file_limit")


async def _shelve_existing_file(
    session_id: str,
    file_id: str,
    *,
    listed: bool,
    artifact: bool,
) -> dict[str, object]:
    cleaned = file_id.strip()
    if not cleaned:
        raise ValueError("room_not_found")
    async with system_rls_session() as db:
        row = await db.get(MindmateCollabBackgroundFile, cleaned)
        if row is None or row.session_id != session_id:
            raise ValueError("room_not_found")
        already_listed = bool(row.listed)
        already_artifact = bool(row.artifact)
    await _ensure_room(
        session_id,
        entering_listed=listed,
        entering_artifact=artifact,
        already_listed=already_listed,
        already_artifact=already_artifact,
    )
    async with system_rls_session() as db:
        row = await db.get(MindmateCollabBackgroundFile, cleaned)
        if row is None or row.session_id != session_id:
            raise ValueError("room_not_found")
        row.listed = listed
        row.artifact = artifact
        await db.commit()
    payload = await get_background_file(session_id, cleaned)
    if payload is None:
        raise ValueError("room_not_found")
    return payload


async def _find_diagram_row(
    session_id: str,
    diagram_id: str,
) -> Optional[tuple[str, bool, bool]]:
    async with system_rls_session() as db:
        result = await db.execute(
            select(MindmateCollabBackgroundFile).where(
                MindmateCollabBackgroundFile.session_id == session_id,
                MindmateCollabBackgroundFile.diagram_id == diagram_id,
            )
        )
        row = result.scalars().first()
        if row is None:
            return None
        return row.id, bool(row.listed), bool(row.artifact)


async def _shelve_diagram(
    session: MindmateCollabSession,
    user: User,
    diagram_id: str,
    title: str,
    *,
    listed: bool,
    artifact: bool,
) -> dict[str, object]:
    cleaned = normalize_canvas_diagram_id(diagram_id)
    if cleaned is None or not await session_contains_canvas_diagram(session.id, cleaned):
        raise ValueError("room_not_found")
    existing = await _find_diagram_row(session.id, cleaned)
    await _ensure_room(
        session.id,
        entering_listed=listed,
        entering_artifact=artifact,
        already_listed=existing[1] if existing else False,
        already_artifact=existing[2] if existing else False,
    )
    if existing is not None:
        return await _shelve_existing_file(
            session.id,
            existing[0],
            listed=listed,
            artifact=artifact,
        )
    body = json.dumps({"diagram_id": cleaned}).encode("utf-8")
    storage_key = await store_background_bytes(f"diagram-{cleaned}.txt", body, "text/plain")
    row = MindmateCollabBackgroundFile(
        id=str(uuid4()),
        session_id=session.id,
        uploader_user_id=int(user.id),
        filename=shelf_title(title),
        content_type=DIAGRAM_REF_TYPE,
        size_bytes=len(body),
        storage_key=storage_key,
        listed=listed,
        artifact=artifact,
        diagram_id=cleaned,
        created_at=datetime.now(tz=UTC),
    )
    try:
        async with system_rls_session() as db:
            db.add(row)
            await db.commit()
    except IntegrityError:
        raced = await _find_diagram_row(session.id, cleaned)
        if raced is None:
            raise
        return await _shelve_existing_file(
            session.id,
            raced[0],
            listed=listed,
            artifact=artifact,
        )
    payload = await get_background_file(session.id, row.id)
    if payload is None:
        raise ValueError("room_not_found")
    return payload
