"""Glasses learning-sheet HTTP routes.

Teacher calls use the signed-in session. The glasses ingest call has no session:
the printed sheet UUID is the key.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from routers.auth.dependencies import get_current_user
from routers.features.learning_space.deps import get_learning_space_db
from services.learning_space.glasses_bind import (
    clear_wearer_bind,
    start_wearer_bind,
    try_accept_wearer_photo,
    wearer_bind_status,
)
from services.learning_space.glasses_copies import assign_class_copies, list_sheet_copies
from services.learning_space.glasses_events import iter_glasses_events, publish_glasses_event
from services.learning_space.glasses_play import (
    drain_glasses_play,
    enqueue_glasses_play,
    glasses_follow_view,
    glasses_owner_id,
    glasses_voice_bytes,
    publish_glasses_slide,
    queue_voice_cue,
    take_queued_recording,
)
from services.redis.redis_client import get_redis
from services.learning_space.glasses_remote import drain_glasses_remote, enqueue_glasses_remote
from services.learning_space.glasses_service import (
    accept_sheet_photo,
    capture_image_for_owner,
    list_captures,
    mint_or_reuse_sheet,
    run_sheet_ocr,
    token_response,
)

router = APIRouter()


class SheetMintRequest(BaseModel):
    """Course diagram bound to a new or existing sheet QR."""

    diagram_id: str = ""
    spec: dict = Field(default_factory=dict)


class SheetCopiesRequest(BaseModel):
    """Class roster to print as numbered pages of one sheet."""

    qr_payload: str = ""
    class_id: int = 0


class RemoteCommand(BaseModel):
    """One canvas nudge from a bound pair of glasses."""

    token: str = ""
    action: str = ""


class PlayCommand(BaseModel):
    """A tap from a bound pair of glasses, asking the computer to advance."""

    token: str = ""
    payload: str = ""


class FollowCommand(BaseModel):
    """The slide the open course is showing."""

    course_id: str = ""
    index: int = -1
    mark: int = 1
    read: int = 0
    done: bool = False
    org_id: int = 0


class VoiceCueCommand(BaseModel):
    """Ask the bound glasses to play the recording saved on this slide."""

    course_id: str = ""
    index: int = 0


@router.post("/glasses/sheets")
async def mint_glasses_sheet(
    body: SheetMintRequest,
    db: AsyncSession = Depends(get_learning_space_db),
    current_user: User = Depends(get_current_user),
):
    """Mint or reuse the QR UUID for this account's diagram."""
    token = await mint_or_reuse_sheet(
        db,
        current_user,
        diagram_id=body.diagram_id,
        spec=body.spec,
    )
    return token_response(token)


@router.post("/glasses/sheets/copies")
async def assign_glasses_sheet_copies(
    body: SheetCopiesRequest,
    db: AsyncSession = Depends(get_learning_space_db),
    current_user: User = Depends(get_current_user),
):
    """Give each student in the class the next sequence number on this sheet."""
    copies = await assign_class_copies(
        db,
        current_user,
        qr_payload=body.qr_payload,
        class_id=int(body.class_id),
    )
    return {"copies": copies}


@router.get("/glasses/sheets/copies")
async def glasses_sheet_copies(
    qr_payload: str = "",
    db: AsyncSession = Depends(get_learning_space_db),
    current_user: User = Depends(get_current_user),
):
    """Which numbered pages exist, and which ones the glasses have photographed."""
    return {"copies": await list_sheet_copies(db, current_user, qr_payload)}


@router.get("/glasses/captures")
async def list_glasses_captures(
    db: AsyncSession = Depends(get_learning_space_db),
    current_user: User = Depends(get_current_user),
):
    """List this account's sheet photos and OCR state."""
    return {"captures": await list_captures(db, current_user)}


@router.get("/glasses/captures/{capture_id}/image")
async def glasses_capture_image(
    capture_id: int,
    db: AsyncSession = Depends(get_learning_space_db),
    current_user: User = Depends(get_current_user),
):
    """Original photo for one capture this account owns."""
    data, mime = await capture_image_for_owner(db, current_user, capture_id)
    return Response(content=data, media_type=mime)


@router.post("/glasses/ingest")
async def ingest_glasses_photo(
    background: BackgroundTasks,
    sheet_uuid: str = Form(...),
    image: UploadFile = File(...),
):
    """Glasses upload. A settings QR binds the wearer. A sheet QR starts OCR."""
    data = await image.read()
    declared = image.content_type or ""
    bound = await try_accept_wearer_photo(sheet_uuid, data, declared)
    if bound is not None:
        return bound
    accepted = await accept_sheet_photo(sheet_uuid, data, declared)
    background.add_task(run_sheet_ocr, int(accepted["capture_id"]))
    return accepted


@router.post("/glasses/remote")
async def post_glasses_remote(body: RemoteCommand):
    """Queue a pan, zoom, or fit for the account that owns this bind token."""
    return await enqueue_glasses_remote(body.token, body.action)


@router.get("/glasses/remote")
async def get_glasses_remote(current_user: User = Depends(get_current_user)):
    """Drain canvas nudges for the editor that is open on this account."""
    return await drain_glasses_remote(int(current_user.id))


@router.post("/glasses/follow")
async def post_glasses_follow(
    body: FollowCommand,
    current_user: User = Depends(get_current_user),
):
    """The open course tells the bound glasses which slide is on screen."""
    published = await publish_glasses_slide(
        int(current_user.id),
        body.course_id,
        body.index,
        body.mark,
        body.read,
        done=body.done,
        organization_id=body.org_id,
    )
    if not published:
        return Response(status_code=503)
    return {"ok": True}


@router.get("/glasses/follow")
async def get_glasses_follow(
    since: int = Query(default=0, ge=0),
    token: str = Header(default="", alias="X-Glasses-Token"),
):
    """The slide the computer is showing, when it is newer than ``since``."""
    body = await glasses_follow_view(token, since)
    if body is None:
        return Response(status_code=204)
    return body


@router.post("/glasses/play")
async def post_glasses_play(body: PlayCommand):
    """A tap asks the computer that owns this bind token to advance."""
    return await enqueue_glasses_play(body.token, body.payload)


@router.get("/glasses/events")
async def glasses_events(request: Request, current_user: User = Depends(get_current_user)):
    """One stream for the open course. A frame means a tap or a canvas nudge is waiting."""

    async def _stream():
        async for chunk in iter_glasses_events(int(current_user.id)):
            if await request.is_disconnected():
                break
            yield chunk

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/glasses/device-events")
async def glasses_device_events(
    request: Request,
    token: str = Header(default="", alias="X-Glasses-Token"),
):
    """The stream a bound pair holds. A frame means the slide or a recording changed."""
    owner = await glasses_owner_id(token)
    if owner is None:
        return Response(status_code=404)

    async def _stream():
        async for chunk in iter_glasses_events(owner):
            if await request.is_disconnected():
                break
            yield chunk

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/glasses/play")
async def get_glasses_play(current_user: User = Depends(get_current_user)):
    """Drain the slide cue for the course builder open on this account."""
    return await drain_glasses_play(int(current_user.id))


@router.post("/glasses/voice/cue")
async def post_glasses_voice_cue(
    body: VoiceCueCommand,
    current_user: User = Depends(get_current_user),
):
    """Queue this slide's glasses recording for the bound pair."""
    owner = int(current_user.id)
    if not queue_voice_cue(get_redis(), owner, body.course_id, body.index):
        return Response(status_code=503)
    await publish_glasses_event(owner, "voice")
    return {"ok": True}


@router.get("/glasses/voice/cue")
async def get_glasses_voice_cue(token: str = Header(default="", alias="X-Glasses-Token")):
    """The recording the editor just sent. Empty when nothing is waiting."""
    audio = await take_queued_recording(token)
    if not audio:
        return Response(status_code=204)
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


@router.get("/glasses/voice")
async def get_glasses_voice(
    course: str = Query(default=""),
    index: int = Query(default=0, ge=0),
    token: str = Header(default="", alias="X-Glasses-Token"),
):
    """The slide recording, for the glasses that are bound to its owner."""
    audio = await glasses_voice_bytes(token, course, index)
    if not audio:
        return Response(status_code=404)
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


@router.post("/glasses/bind")
async def start_glasses_bind(
    db: AsyncSession = Depends(get_learning_space_db),
    current_user: User = Depends(get_current_user),
):
    """Mint the QR shown in Settings for this account."""
    return await start_wearer_bind(db, current_user)


@router.get("/glasses/bind")
async def glasses_bind_state(
    token: str = "",
    db: AsyncSession = Depends(get_learning_space_db),
    current_user: User = Depends(get_current_user),
):
    """Whether the glasses have photographed this account's QR."""
    return await wearer_bind_status(db, current_user, token)


@router.post("/glasses/bind/unbind")
async def unbind_glasses(
    db: AsyncSession = Depends(get_learning_space_db),
    current_user: User = Depends(get_current_user),
):
    """Remove the glasses link from this account."""
    await clear_wearer_bind(db, current_user)
    return {"linked": False}
